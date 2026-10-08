"""
Match Processing Tasks

Tasks for processing match data from the match-scraper service.
These tasks run asynchronously in Celery workers, allowing for:
- Non-blocking match data ingestion
- Automatic retries on failure
- Horizontal scaling of processing capacity
"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import Task

from celery_app import app
from celery_tasks.exceptions import UnresolvedNameError
from celery_tasks.validation_tasks import validate_match_data
from dao.club_dao import ClubDAO
from dao.ingest_failures_dao import IngestFailuresDAO
from dao.league_dao import LeagueDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.match_type_dao import MatchTypeDAO
from dao.season_dao import SeasonDAO
from dao.team_dao import TeamDAO
from logging_config import get_logger
from notifications.ingest_alerts import alert_unresolved_name

logger = get_logger(__name__)

# The zone a zone-less match_time is read in when nothing better is known.
DEFAULT_KICKOFF_TZ = "America/New_York"


class DatabaseTask(Task):
    """
    Base task class that provides database access.

    The DAO and connection attributes are class-level so they're shared
    across all task executions in the same worker process.
    """

    _connection = None
    _dao = None
    _team_dao = None
    _season_dao = None
    _league_dao = None
    _match_type_dao = None
    _ingest_failures_dao = None
    _club_dao = None

    # Names this worker has already confirmed good, so the "did this name used
    # to fail?" check costs one round trip per distinct name per worker rather
    # than one per match. A season load sees tens of names across thousands of
    # matches, so the difference is thousands of calls.
    _resolved_names: set[tuple[str, str]] = set()

    # (team_id, age_group_id, division_id) triples this worker has already
    # registered. Same reasoning as _resolved_names: a season load is thousands
    # of matches over a couple of dozen triples, and checking per match would be
    # thousands of round trips to learn the same thing.
    _ensured_mappings: set[tuple[int, int, int]] = set()

    @property
    def dao(self):
        """Lazy initialization of MatchDAO to avoid creating connections at import time."""
        if self._dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._dao = MatchDAO(self._connection)
        return self._dao

    @property
    def team_dao(self):
        """Lazy initialization of TeamDAO for team lookups."""
        if self._team_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._team_dao = TeamDAO(self._connection)
        return self._team_dao

    @property
    def season_dao(self):
        """Lazy initialization of SeasonDAO for season/age-group lookups."""
        if self._season_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._season_dao = SeasonDAO(self._connection)
        return self._season_dao

    @property
    def league_dao(self):
        """Lazy initialization of LeagueDAO for division lookups."""
        if self._league_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._league_dao = LeagueDAO(self._connection)
        return self._league_dao

    @property
    def match_type_dao(self):
        """Lazy initialization of MatchTypeDAO for competition lookups."""
        if self._match_type_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._match_type_dao = MatchTypeDAO(self._connection)
        return self._match_type_dao

    @property
    def ingest_failures_dao(self):
        """Lazy initialization of IngestFailuresDAO for unresolved-name reporting."""
        if self._ingest_failures_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._ingest_failures_dao = IngestFailuresDAO(self._connection)
        return self._ingest_failures_dao

    @property
    def club_dao(self):
        """Lazy initialization of ClubDAO for the home club's timezone."""
        if self._club_dao is None:
            if self._connection is None:
                self._connection = SupabaseConnection()
            self._club_dao = ClubDAO(self._connection)
        return self._club_dao

    def _note_name_resolved(self, kind: str, raw_name: str, source: str) -> None:
        """Close any open ingest_failures row for a name that now resolves.

        Called on the success path so that adding an alias mid-load clears its
        own alert without anyone touching the table.
        """
        key = (kind, raw_name.lower())
        if key in self._resolved_names:
            return
        self._resolved_names.add(key)
        self.ingest_failures_dao.resolve(kind, raw_name, source=source)

    def _register_team_age_group(self, team: dict[str, Any], age_group_id: int | None, division: dict | None) -> None:
        """Record that this team plays this age group, in this division.

        Nothing on the ingest path used to do this, so a team the scraper had
        been filing matches for all season did not exist at that age group as
        far as the product was concerned: /api/teams builds a team's age_groups
        purely from team_mappings, and the My Club team picker filters on it.
        NEFC had 44 U15 matches and an empty U15 team picker (SB-852).

        Only the team's **own** league registers a mapping. A Homegrown team's
        Flex matches carry the Flex bracket's division_id, and writing that
        would give the team two divisions at one age group — while
        divisions_by_age_group is keyed by age group alone and takes last-wins,
        so the team's division would start displaying as a Flex bracket. Flex
        participation is already expressed by the matches, and Flex standings
        read matches directly (SB-835).

        A team with no league_id yet is registered anyway: that is a team whose
        first mapping this is, and refusing would leave it stuck with none.
        """
        if not division or age_group_id is None:
            return

        division_id = division.get("id")
        if division_id is None:
            return

        team_league_id = team.get("league_id")
        if team_league_id is not None and division.get("league_id") != team_league_id:
            return

        key = (team["id"], age_group_id, division_id)
        if key in self._ensured_mappings:
            return
        self._ensured_mappings.add(key)

        if self.team_dao.ensure_team_mapping(team["id"], age_group_id, division_id):
            logger.info(
                "Registered team age group",
                team_id=team["id"],
                age_group_id=age_group_id,
                division_id=division_id,
            )

    def _resolve_season_id(self, match_data: dict[str, Any]) -> int:
        """The season the message names, not the one the calendar is on.

        A match belongs to the season it was played in. Filing by the current
        season instead makes every historical load land in the wrong year, and
        puts a May fixture re-scraped in August into the new season (SB-882).

        Falls back to the current season when the message names none or names
        one MT does not have, and says so — a silent fallback is how 151
        matches with 2025-2026 dates ended up in 2026-2027.
        """
        named = (match_data.get("season") or "").strip()
        if named:
            season = self.season_dao.get_season_by_name(named)
            if season:
                return season["id"]
            logger.warning(
                "Unknown season in message, falling back to current",
                season=named,
                external_match_id=match_data.get("external_match_id"),
            )

        current_season = self.season_dao.get_current_season()
        return current_season["id"] if current_season else 1

    @staticmethod
    def _read_shootout(match_data: dict[str, Any]) -> tuple[int | None, int | None]:
        """The penalty shootout on the message, if it is one the DB will accept.

        MLS NEXT Flex fixtures cannot end level — a regulation draw is decided
        on penalties (SB-1019/SB-1020). The matches table has carried the pair
        since the tournament work, under two CHECK constraints: both columns or
        neither, and only when regulation ended level.

        A message that breaks either is reported and its shootout dropped,
        rather than raised: the alternative loses a real fixture over a field
        that is decoration on the scoreline. The scraper filters both shapes
        before sending, so anything arriving here came from somewhere else.
        """
        home_pens = match_data.get("home_penalty_score")
        away_pens = match_data.get("away_penalty_score")
        if home_pens is None and away_pens is None:
            return None, None

        label = (
            f"{match_data.get('home_team')} vs {match_data.get('away_team')} ({match_data.get('external_match_id')})"
        )
        if home_pens is None or away_pens is None:
            logger.warning(
                "Ignoring half a penalty shootout",
                match=label,
                home_penalty_score=home_pens,
                away_penalty_score=away_pens,
            )
            return None, None

        home_score = match_data.get("home_score")
        away_score = match_data.get("away_score")
        if home_score is None or away_score is None or home_score != away_score:
            logger.warning(
                "Ignoring a penalty shootout on a match that was not level",
                match=label,
                score=f"{home_score}-{away_score}",
                shootout=f"{home_pens}-{away_pens}",
            )
            return None, None

        return home_pens, away_pens

    @staticmethod
    def _feed_kickoff(match_data: dict[str, Any]) -> str | None:
        """The feed's own kickoff instant, as a UTC ISO 8601 string (SB-1203).

        match-scraper sends ``scheduled_kickoff`` straight from the feed's UTC
        ``start_time``. It is exact, so it beats any reading of match_time.
        A value without an offset, or one that doesn't parse, is ignored with a
        warning: guessing its zone is the bug this replaces (SB-1202).
        """
        raw = match_data.get("scheduled_kickoff")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Ignoring an unparseable scheduled_kickoff", scheduled_kickoff=raw)
            return None
        if parsed.tzinfo is None:
            logger.warning("Ignoring a scheduled_kickoff with no UTC offset", scheduled_kickoff=raw)
            return None
        return parsed.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    @staticmethod
    def _build_scheduled_kickoff(match_data: dict[str, Any], venue_tz: str = DEFAULT_KICKOFF_TZ) -> str | None:
        """Combine match_date + match_time into a UTC ISO 8601 timestamp for scheduled_kickoff.

        match_time is the venue's local wall-clock time, not US Eastern: the
        feed converts its UTC start to the event's own timezone (SB-1202).
        ``venue_tz`` is the IANA zone to read it in; an unknown name falls back
        to Eastern with a warning.

        Returns None if match_time is absent or null.
        """
        match_time = match_data.get("match_time")
        match_date = match_data.get("match_date")
        if match_time and match_date:
            try:
                zone = ZoneInfo(venue_tz)
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning("Unknown kickoff timezone, reading match_time as Eastern", timezone=venue_tz)
                zone = ZoneInfo(DEFAULT_KICKOFF_TZ)
            naive = datetime.strptime(f"{match_date} {match_time}", "%Y-%m-%d %H:%M")
            local_dt = naive.replace(tzinfo=zone)
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        return None

    def _home_timezone(self, home_team_id: int | None) -> str:
        """The home club's IANA timezone, or Eastern when it can't be found."""
        if home_team_id is None:
            return DEFAULT_KICKOFF_TZ
        try:
            club = self.club_dao.get_club_for_team(home_team_id)
        except Exception as exc:
            logger.warning("Home club timezone lookup failed", home_team_id=home_team_id, error=str(exc))
            return DEFAULT_KICKOFF_TZ
        return (club or {}).get("timezone") or DEFAULT_KICKOFF_TZ

    def _resolve_kickoff(self, match_data: dict[str, Any], home_team_id: int | None) -> str | None:
        """The UTC kickoff to store: the feed's instant, else match_time read in the home club's zone.

        The club lookup only happens on the fallback path, so a payload that
        carries scheduled_kickoff costs no extra query.
        """
        feed_kickoff = self._feed_kickoff(match_data)
        if feed_kickoff:
            return feed_kickoff
        if not (match_data.get("match_time") and match_data.get("match_date")):
            return None
        return self._build_scheduled_kickoff(match_data, self._home_timezone(home_team_id))

    def _match_type_label(self, match_type_id: int | None) -> str:
        """A competition's name for a log line, falling back to its id."""
        if match_type_id is None:
            return "none"
        row = self.match_type_dao.get_match_type_by_id(match_type_id)
        return (row or {}).get("name") or str(match_type_id)

    @staticmethod
    def _feed_owns_filing(existing_match: dict[str, Any]) -> bool:
        """Whether the feed gets to re-file this match's competition and division.

        Scraped data wins on results, and competition and division arrive from
        the feed the same way scores do — so a correction should land. A match
        somebody entered by hand is the exception: a friendly recorded against
        a league fixture's external id is a deliberate choice, and silently
        re-filing it would be the product overruling its user.

        Adoption flips the answer rather than being a special case — populating
        an external id on a manual match stamps source='match-scraper' — so
        this reads the row's current owner, not how it was born.

        A row with no source at all predates the column's use on this path and
        is treated as the feed's, which is what it is.
        """
        return (existing_match.get("source") or "match-scraper") == "match-scraper"

    # Statuses a person sets. The scraper derives status from date and score,
    # and says postponed only for a fixture parked on the feed's placeholder
    # date (SB-1136) — it can never say one was played-but-void or cancelled.
    HELD_STATUSES = frozenset({"postponed", "cancelled"})

    @staticmethod
    def _incoming_date(existing_match: dict[str, Any], new_data: dict[str, Any]) -> str | None:
        """The new match_date to write, or None to leave the row's date alone.

        A postponed fixture is parked by MLS NEXT on a placeholder date (in
        2026-2027, Tuesday 8 June 2027: 103 fixtures and nothing else that day).
        That date is not a reschedule, and copying it would stack every
        postponement on one fake Tuesday and lose the date the match was due.
        So a postponed message never moves the date; the next real date does
        (SB-1136).
        """
        if new_data.get("match_status") == "postponed":
            return None
        new_date = new_data.get("match_date")
        existing_date = existing_match.get("match_date")
        if new_date and existing_date and new_date != existing_date:
            return new_date
        return None

    @classmethod
    def _incoming_status(cls, existing_match: dict[str, Any], new_data: dict[str, Any]) -> str | None:
        """The status a re-scrape should leave on the row (SB-1135).

        A postponed or cancelled status may have been set by a person, and the
        feed cannot say cancelled at all. A postponed fixture still sitting on its old date with
        no score reads to the scraper as "played, score pending", so it arrived
        as tbd and silently undid the human's call.

        The held status gives way only to evidence the feed can actually carry:
        a real score (the match was played) or a new date (it was rescheduled,
        and the feed's status for the new date is the right one).
        """
        new_status = new_data.get("match_status")
        existing_status = existing_match.get("match_status")

        # A result already on the row outranks the feed calling the match off
        # (SB-1136): a live-scored match is not un-played by a placeholder date.
        if new_status == "postponed" and existing_status in ("completed", "forfeit"):
            return existing_status

        if existing_status not in cls.HELD_STATUSES:
            return new_status

        if new_data.get("home_score") is not None and new_data.get("away_score") is not None:
            return new_status

        if cls._incoming_date(existing_match, new_data):
            return new_status

        return existing_match["match_status"]

    def _check_needs_update(
        self,
        existing_match: dict[str, Any],
        new_data: dict[str, Any],
        home_team_id: int,
        away_team_id: int,
        match_type_id: int | None = None,
        division_id: int | None = None,
    ) -> bool:
        """
        Check if the existing match needs to be updated based on new data.

        Returns True if any of these conditions are met:
        - Home/away teams swapped (home_team_id or away_team_id differ)
        - Status changed (scheduled → tbd, tbd → completed, etc.)
        - Scores changed (were null, now have values)
        - Scores were updated (different values)
        - Competition or division changed (SB-847)

        Status transition examples:
        - scheduled → tbd: Match played, awaiting score
        - tbd → tbd: No change (skip)
        - tbd → completed: Score posted (update with scores)
        - scheduled → completed: Direct completion (skip tbd)

        Competition and division were not compared until SB-847, which made a
        wrongly-filed match impossible to correct by re-scraping: the row was
        found, nothing recognised as changed, and the run reported success. 68
        Flex fixtures sat in prod as League through three clean re-submits.
        """
        # Check competition / division re-filing (SB-847)
        if self._feed_owns_filing(existing_match):
            if match_type_id is not None and existing_match.get("match_type_id") != match_type_id:
                logger.debug(f"match_type changed: {existing_match.get('match_type_id')} → {match_type_id}")
                return True
            if division_id is not None and existing_match.get("division_id") != division_id:
                logger.debug(f"division changed: {existing_match.get('division_id')} → {division_id}")
                return True

        # Check home/away team swap
        if existing_match.get("home_team_id") != home_team_id or existing_match.get("away_team_id") != away_team_id:
            logger.debug(
                f"Team assignment changed: home {existing_match.get('home_team_id')} → {home_team_id}, "
                f"away {existing_match.get('away_team_id')} → {away_team_id}"
            )
            return True

        # Check status change
        existing_status = existing_match.get("match_status", "scheduled")
        new_status = self._incoming_status(existing_match, new_data) or "scheduled"
        if existing_status != new_status:
            logger.debug(f"Status changed: {existing_status} → {new_status}")
            return True

        # Check score changes
        existing_home_score = existing_match.get("home_score")
        existing_away_score = existing_match.get("away_score")
        new_home_score = new_data.get("home_score")
        new_away_score = new_data.get("away_score")

        # If new data has scores and they differ from existing
        if new_home_score is not None and new_away_score is not None:
            if existing_home_score != new_home_score or existing_away_score != new_away_score:
                logger.debug(
                    f"Scores changed: {existing_home_score}-{existing_away_score} → {new_home_score}-{new_away_score}"
                )
                return True

        # Check the penalty shootout (SB-1020). Without this a fixture whose
        # score was already right but whose shootout was missing — every Flex
        # draw ingested before this shipped — reads as unchanged and is never
        # corrected, the same trap SB-847 documented above.
        new_pens = self._read_shootout(new_data)
        if new_pens != (None, None):
            existing_pens = (
                existing_match.get("home_penalty_score"),
                existing_match.get("away_penalty_score"),
            )
            if existing_pens != new_pens:
                logger.debug(f"Penalty shootout changed: {existing_pens} → {new_pens}")
                return True

        # Check if match_date changed (rescheduled match)
        new_date = self._incoming_date(existing_match, new_data)
        if new_date:
            logger.debug(f"match_date changed: {existing_match.get('match_date')} → {new_date}")
            return True

        # Check if scheduled_kickoff can be set/updated from the feed
        new_kickoff = self._resolve_kickoff(new_data, home_team_id)
        existing_kickoff = existing_match.get("scheduled_kickoff")
        if new_kickoff and new_kickoff != existing_kickoff:
            logger.debug(f"scheduled_kickoff changed: {existing_kickoff} → {new_kickoff}")
            return True

        return False

    def _update_match_scores(
        self,
        existing_match: dict[str, Any],
        new_data: dict[str, Any],
        home_team_id: int | None = None,
        away_team_id: int | None = None,
        match_type_id: int | None = None,
        division_id: int | None = None,
    ) -> bool:
        """
        Update an existing match's scores, status, team assignments and filing.

        Updates scores, status, match_date, scheduled_kickoff,
        home_team_id/away_team_id when a home/away swap is detected, and
        match_type_id/division_id when the feed re-files the match (SB-847).
        """
        try:
            match_id = existing_match["id"]

            # Prepare update data
            update_data: dict[str, object] = {}

            # Correct competition and division. Logged by name, not id: a line
            # reading "match_type corrected: 1 → 5" tells nobody that a fixture
            # moved from League to Flex, and the whole point of this is that a
            # competition move stops being silent.
            if self._feed_owns_filing(existing_match):
                if match_type_id is not None and match_type_id != existing_match.get("match_type_id"):
                    update_data["match_type_id"] = match_type_id
                    logger.info(
                        f"Match {match_id} match_type corrected: "
                        f"{self._match_type_label(existing_match.get('match_type_id'))} → "
                        f"{self._match_type_label(match_type_id)}"
                    )
                if division_id is not None and division_id != existing_match.get("division_id"):
                    update_data["division_id"] = division_id
                    logger.info(
                        f"Match {match_id} division corrected: {existing_match.get('division_id')} → {division_id}"
                    )

            # Correct home/away team swap if team IDs differ
            if home_team_id is not None and home_team_id != existing_match.get("home_team_id"):
                update_data["home_team_id"] = home_team_id
                logger.info(
                    f"Match {match_id} home_team_id corrected: {existing_match.get('home_team_id')} → {home_team_id}"
                )
            if away_team_id is not None and away_team_id != existing_match.get("away_team_id"):
                update_data["away_team_id"] = away_team_id
                logger.info(
                    f"Match {match_id} away_team_id corrected: {existing_match.get('away_team_id')} → {away_team_id}"
                )

            # Update scores if provided
            if new_data.get("home_score") is not None:
                update_data["home_score"] = new_data["home_score"]
            if new_data.get("away_score") is not None:
                update_data["away_score"] = new_data["away_score"]

            # Update the penalty shootout, both columns together (SB-1020).
            home_pens, away_pens = self._read_shootout(new_data)
            if home_pens is not None and away_pens is not None:
                update_data["home_penalty_score"] = home_pens
                update_data["away_penalty_score"] = away_pens

            # Update status if provided, unless a person's postponed/cancelled
            # still stands (SB-1135)
            new_status = self._incoming_status(existing_match, new_data)
            if new_status:
                update_data["match_status"] = new_status

            # Update match_date if changed (rescheduled match)
            new_date = self._incoming_date(existing_match, new_data)
            if new_date:
                update_data["match_date"] = new_date
                logger.info(f"Match {match_id} rescheduled: {existing_match.get('match_date')} → {new_date}")

            # Update scheduled_kickoff if the feed gives one and it differs
            new_kickoff = self._resolve_kickoff(
                new_data, home_team_id if home_team_id is not None else existing_match.get("home_team_id")
            )
            if new_kickoff and new_kickoff != existing_match.get("scheduled_kickoff"):
                update_data["scheduled_kickoff"] = new_kickoff

            # Note: updated_by field expects UUID, not string.
            # For match-scraper updates, we'll skip this field since it's optional.
            # If we need to track match-scraper updates, we should use 'source' field instead.

            if not update_data:
                logger.warning(f"No update data provided for match {match_id}")
                return False

            # Execute update directly on matches table
            response = self.dao.client.table("matches").update(update_data).eq("id", match_id).execute()

            if response.data:
                logger.info(f"Successfully updated match {match_id}: {update_data}")
                return True
            else:
                logger.error(f"Update returned no data for match {match_id}")
                return False

        except Exception as e:
            logger.error(f"Error updating match scores: {e}", exc_info=True)
            return False


@app.task(
    bind=True,
    base=DatabaseTask,
    name="celery_tasks.match_tasks.process_match_data",
    max_retries=3,
    default_retry_delay=60,  # Retry after 1 minute
    autoretry_for=(Exception,),  # Auto-retry on any exception
    # ...except a name that does not exist. Waiting ten minutes will not make
    # an unknown team known; retrying three times only delays the moment
    # anyone finds out (SB-829).
    dont_autoretry_for=(UnresolvedNameError,),
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes backoff
    retry_jitter=True,  # Add random jitter to prevent thundering herd
)
def process_match_data(self: DatabaseTask, match_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process match data from match-scraper and insert into database.

    This task:
    1. Validates the match data
    2. Extracts/creates teams if needed
    3. Inserts or updates the match in the database
    4. Returns the created/updated match ID

    Args:
        match_data: Dictionary containing match information
            Required fields:
            - home_team: str
            - away_team: str
            - match_date: str (ISO format)
            - season: str
            - age_group: str
            - division: str
            Optional fields:
            - home_score: int
            - away_score: int
            - match_status: str
            - match_type: str
            - location: str
            - match_time: str ("HH:MM", the venue's local time)
            - scheduled_kickoff: str (ISO 8601 with offset, the feed's UTC
              kickoff; preferred over match_time when present)

    Returns:
        Dict containing:
        - match_id: int - The database ID of the created/updated match
        - status: str - 'created' or 'updated'
        - message: str - Success message

    Raises:
        ValidationError: If match data is invalid
        DatabaseError: If database operation fails
    """
    try:
        mls_id = match_data.get("external_match_id", "N/A")
        logger.info(
            f"Processing match data: {match_data.get('home_team')} vs {match_data.get('away_team')} (MLS ID: {mls_id})"
        )

        # Step 1: Validate the match data
        validation_result = validate_match_data(match_data)
        if not validation_result["valid"]:
            error_msg = f"Invalid match data: {validation_result['errors']}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Step 2: Extract team information
        home_team_name = match_data["home_team"]
        away_team_name = match_data["away_team"]

        # The feed's competition name scopes both lookups below. Team aliases
        # and division names are unique per league, not globally, so resolving
        # the league first is what keeps two competitions that share a name
        # ("Florida" is a Homegrown division and a Flex one) apart.
        league_name = match_data.get("league")
        league_id = None
        if league_name:
            league_record = self.league_dao.get_league_by_name(league_name)
            if league_record:
                league_id = league_record["id"]
            else:
                logger.warning(f"League '{league_name}' not found - name lookups will not be league-scoped")

        logger.debug(f"Looking up teams: {home_team_name}, {away_team_name} (league_id={league_id})")

        # Resolve teams. resolve_team_by_name consults team_aliases as well as
        # teams.name (SB-822) — the plain name lookup this used to call meant
        # the aliases seeded for the Kitman feed never applied to the feed.
        # Nothing is created here: an unknown name fails the task rather than
        # inventing a lightweight team row that later collides on the unique
        # constraint.
        sample = (
            f"{home_team_name} vs {away_team_name}, {match_data.get('match_date')} {match_data.get('age_group', '')}"
        ).strip()

        home_team = self.team_dao.resolve_team_by_name(home_team_name, league_id=league_id)
        if not home_team:
            raise UnresolvedNameError("team", home_team_name, league=league_name, sample=sample)

        away_team = self.team_dao.resolve_team_by_name(away_team_name, league_id=league_id)
        if not away_team:
            raise UnresolvedNameError("team", away_team_name, league=league_name, sample=sample)

        # Both names are good. If either was failing before — an alias added
        # part way through a load, say — close its row now.
        source = match_data.get("source") or "match-scraper"
        self._note_name_resolved("team", home_team_name, source)
        self._note_name_resolved("team", away_team_name, source)

        # Step 2b: Resolve how the feed files this match — competition and
        # division — before the create/update fork.
        #
        # Both used to be resolved only on the create branch, which is half of
        # why a wrongly-filed match could not be corrected by re-scraping
        # (SB-847). The other half was that create ignored the feed's
        # competition entirely and wrote match_type_id 1: 68 Flex fixtures
        # went into prod as League (SB-846) and three clean re-submits could
        # not move them.
        match_type_id = None
        match_type_name = match_data.get("match_type")
        if match_type_name:
            match_type_record = self.match_type_dao.get_match_type_by_name(match_type_name)
            if not match_type_record:
                # Same reasoning as an unknown division below: defaulting to
                # League is exactly the failure this ticket exists to end.
                raise UnresolvedNameError(
                    "match_type",
                    match_type_name,
                    league=league_name,
                    sample=sample,
                )
            match_type_id = match_type_record["id"]
            self._note_name_resolved("match_type", match_type_name, source)

        division_record = None
        division_id = None
        if match_data.get("division"):
            div_record = self.league_dao.get_division_by_name(match_data["division"], league_id=league_id)
            if div_record:
                division_record = div_record
                division_id = div_record["id"]
            else:
                # Writing NULL here used to look like a warning and behave
                # like data loss: get_league_table filters on division, so
                # the match existed but appeared in no table at all.
                raise UnresolvedNameError(
                    "division",
                    match_data["division"],
                    league=league_name,
                    sample=sample,
                )

        age_group_id = None
        if match_data.get("age_group"):
            age_group_record = self.season_dao.get_age_group_by_name(match_data["age_group"])
            if age_group_record:
                age_group_id = age_group_record["id"]
            else:
                logger.warning(f"Age group not found: {match_data['age_group']}")

        # Record that both teams play this age group in this division. Nothing
        # did, so a team the scraper had filed matches for all season did not
        # exist at that age group as far as the team pickers were concerned
        # (SB-852).
        self._register_team_age_group(home_team, age_group_id, division_record)
        self._register_team_age_group(away_team, age_group_id, division_record)

        # Step 3: Check if match already exists
        external_match_id = match_data.get("external_match_id")
        existing_match = None

        # First try: Look up by external ID (fast path for previously scraped matches)
        if external_match_id:
            existing_match = self.dao.get_match_by_external_id(external_match_id)
            logger.debug(
                f"Lookup by external_match_id '{external_match_id}': {'found' if existing_match else 'not found'}"
            )

        # Second try: Fallback to lookup by teams + date + age_group (for manually-entered matches)
        if not existing_match:
            existing_match = self.dao.get_match_by_teams_and_date(
                home_team_id=home_team["id"],
                away_team_id=away_team["id"],
                match_date=match_data["match_date"],
                age_group_id=age_group_id,
            )

            if existing_match:
                logger.info(
                    f"Found manually-entered match via fallback lookup: "
                    f"{home_team_name} vs {away_team_name} on {match_data['match_date']}"
                    + (f" ({match_data['age_group']})" if match_data.get("age_group") else "")
                )

                # If found a match without external_match_id, populate it
                if external_match_id and not existing_match.get("match_id"):
                    logger.info(f"Populating match_id '{external_match_id}' on existing match {existing_match['id']}")
                    success = self.dao.update_match_external_id(
                        match_id=existing_match["id"], external_match_id=external_match_id
                    )
                    if success:
                        # Update the existing_match dict to reflect the new match_id
                        existing_match["match_id"] = external_match_id
                        existing_match["source"] = "match-scraper"
                        logger.info(f"Successfully populated match_id on match {existing_match['id']}")
                    else:
                        logger.warning(f"Failed to populate match_id on match {existing_match['id']}")

        # Step 4: Insert or update match
        if existing_match:
            # Check if this is a score update
            needs_update = self._check_needs_update(
                existing_match,
                match_data,
                home_team["id"],
                away_team["id"],
                match_type_id=match_type_id,
                division_id=division_id,
            )

            if needs_update:
                logger.info(
                    f"Updating existing match DB ID {existing_match['id']} (MLS ID: {external_match_id}): "
                    f"{home_team_name} vs {away_team_name}"
                )
                success = self._update_match_scores(
                    existing_match,
                    match_data,
                    home_team["id"],
                    away_team["id"],
                    match_type_id=match_type_id,
                    division_id=division_id,
                )

                if success:
                    result = {
                        "db_id": existing_match["id"],
                        "mls_id": external_match_id,
                        "status": "updated",
                        "message": f"Updated match scores: {home_team_name} vs {away_team_name}",
                    }
                else:
                    raise Exception(f"Failed to update match {existing_match['id']}")
            else:
                logger.info(
                    f"Match already exists with DB ID {existing_match['id']} (MLS ID: {external_match_id}). "
                    "No changes needed."
                )
                result = {
                    "db_id": existing_match["id"],
                    "mls_id": external_match_id,
                    "status": "skipped",
                    "message": f"Match unchanged: {home_team_name} vs {away_team_name}",
                }
        else:
            logger.info(f"Creating new match (MLS ID: {external_match_id}): {home_team_name} vs {away_team_name}")

            # Resolve names to IDs before calling create_match
            season_id = self._resolve_season_id(match_data)

            # Resolved once above, for both branches. 1 remains the fallback
            # for a feed that names an age group we do not have.
            age_group_id_for_create = age_group_id or 1

            scheduled_kickoff = self._resolve_kickoff(match_data, home_team["id"])
            home_pens, away_pens = self._read_shootout(match_data)

            match_id = self.dao.create_match(
                home_team_id=home_team["id"],
                away_team_id=away_team["id"],
                match_date=match_data["match_date"],
                season_id=season_id,
                home_score=match_data.get("home_score"),
                away_score=match_data.get("away_score"),
                match_status=match_data.get("match_status", "scheduled"),
                # The message says where it came from — a backfill or a manual
                # entry is not a scraper run, and rule 6 wants that queryable.
                source=match_data.get("source") or "match-scraper",
                match_id=external_match_id,
                age_group_id=age_group_id_for_create,
                division_id=division_id,
                match_type_id=match_type_id,
                scheduled_kickoff=scheduled_kickoff,
                home_penalty_score=home_pens,
                away_penalty_score=away_pens,
            )
            if match_id:
                result = {
                    "db_id": match_id,
                    "mls_id": external_match_id,
                    "status": "created",
                    "message": f"Created match: {home_team_name} vs {away_team_name}",
                }
            else:
                raise Exception("Failed to create match")

        logger.info(f"Successfully processed match: {result}")
        return result

    except UnresolvedNameError as e:
        # Permanent. Record it so the name is reported once with a count
        # rather than once per dropped match, alert if it is newly seen, and
        # fail without retrying (dont_autoretry_for above).
        logger.warning(
            "Match dropped — unresolved name",
            kind=e.kind,
            raw_name=e.raw_name,
            league=e.league,
        )
        record = self.ingest_failures_dao.record(
            e.kind,
            e.raw_name,
            league=e.league,
            source=match_data.get("source") or "match-scraper",
            sample=e.sample,
        )
        alert_unresolved_name(
            self.ingest_failures_dao,
            kind=e.kind,
            raw_name=e.raw_name,
            league=e.league,
            sample=e.sample,
            record=record,
        )
        raise

    except Exception as e:
        logger.error(f"Error processing match data: {e}", exc_info=True)
        # Celery will auto-retry based on configuration
        raise
