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
from zoneinfo import ZoneInfo

from celery import Task

from celery_app import app
from celery_tasks.validation_tasks import validate_match_data
from dao.league_dao import LeagueDAO
from dao.match_dao import MatchDAO, SupabaseConnection
from dao.season_dao import SeasonDAO
from dao.team_dao import TeamDAO
from logging_config import get_logger

logger = get_logger(__name__)


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

    @staticmethod
    def _build_scheduled_kickoff(match_data: dict[str, Any]) -> str | None:
        """Combine match_date + match_time into a UTC ISO 8601 timestamp for scheduled_kickoff.

        MLS Next displays all times in US Eastern.  We interpret match_time as
        Eastern, convert to UTC, and return an ISO string suitable for a
        Supabase ``timestamptz`` column.

        Returns None if match_time is absent or null.
        """
        match_time = match_data.get("match_time")
        match_date = match_data.get("match_date")
        if match_time and match_date:
            eastern = ZoneInfo("America/New_York")
            naive = datetime.strptime(f"{match_date} {match_time}", "%Y-%m-%d %H:%M")
            eastern_dt = naive.replace(tzinfo=eastern)
            utc_dt = eastern_dt.astimezone(ZoneInfo("UTC"))
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        return None

    def _check_needs_update(self, existing_match: dict[str, Any], new_data: dict[str, Any]) -> bool:
        """
        Check if the existing match needs to be updated based on new data.

        Returns True if any of these conditions are met:
        - Status changed (scheduled → tbd, tbd → completed, etc.)
        - Scores changed (were null, now have values)
        - Scores were updated (different values)

        Status transition examples:
        - scheduled → tbd: Match played, awaiting score
        - tbd → tbd: No change (skip)
        - tbd → completed: Score posted (update with scores)
        - scheduled → completed: Direct completion (skip tbd)
        """
        # Check status change
        existing_status = existing_match.get("match_status", "scheduled")
        new_status = new_data.get("match_status", "scheduled")
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

        # Check if scheduled_kickoff can be set/updated from match_time
        new_kickoff = self._build_scheduled_kickoff(new_data)
        existing_kickoff = existing_match.get("scheduled_kickoff")
        if new_kickoff and new_kickoff != existing_kickoff:
            logger.debug(f"scheduled_kickoff changed: {existing_kickoff} → {new_kickoff}")
            return True

        return False

    def _update_match_scores(self, existing_match: dict[str, Any], new_data: dict[str, Any]) -> bool:
        """
        Update an existing match's scores and status.

        This is a simplified update that only changes scores and status,
        preserving all other match data.
        """
        try:
            match_id = existing_match["id"]

            # Prepare update data
            update_data = {}

            # Update scores if provided
            if new_data.get("home_score") is not None:
                update_data["home_score"] = new_data["home_score"]
            if new_data.get("away_score") is not None:
                update_data["away_score"] = new_data["away_score"]

            # Update status if provided
            if new_data.get("match_status"):
                update_data["match_status"] = new_data["match_status"]

            # Update scheduled_kickoff if match_time provided and different
            new_kickoff = self._build_scheduled_kickoff(new_data)
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

        logger.debug(f"Looking up teams: {home_team_name}, {away_team_name}")

        # Get or create teams
        home_team = self.team_dao.get_team_by_name(home_team_name)
        if not home_team:
            logger.warning(f"Home team not found: {home_team_name}. Creating placeholder.")
            raise ValueError(f"Team not found: {home_team_name}")

        away_team = self.team_dao.get_team_by_name(away_team_name)
        if not away_team:
            logger.warning(f"Away team not found: {away_team_name}. Creating placeholder.")
            raise ValueError(f"Team not found: {away_team_name}")

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
            # Look up age_group_id if age_group is provided
            age_group_id = None
            if match_data.get("age_group"):
                age_group = self.season_dao.get_age_group_by_name(match_data["age_group"])
                if age_group:
                    age_group_id = age_group["id"]
                else:
                    logger.warning(f"Age group not found: {match_data['age_group']}")

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
            needs_update = self._check_needs_update(existing_match, match_data)

            if needs_update:
                logger.info(
                    f"Updating existing match DB ID {existing_match['id']} (MLS ID: {external_match_id}): "
                    f"{home_team_name} vs {away_team_name}"
                )
                success = self._update_match_scores(existing_match, match_data)

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
            current_season = self.season_dao.get_current_season()
            season_id = current_season["id"] if current_season else 1

            age_group_id_for_create = 1  # Default fallback
            if match_data.get("age_group"):
                ag_record = self.season_dao.get_age_group_by_name(match_data["age_group"])
                if ag_record:
                    age_group_id_for_create = ag_record["id"]
                else:
                    logger.warning(f"Age group '{match_data['age_group']}' not found, using default ID 1")

            division_id_for_create = None
            if match_data.get("division"):
                div_record = self.league_dao.get_division_by_name(match_data["division"])
                if div_record:
                    division_id_for_create = div_record["id"]
                else:
                    logger.error(f"Division '{match_data['division']}' not found in database")

            scheduled_kickoff = self._build_scheduled_kickoff(match_data)

            match_id = self.dao.create_match(
                home_team_id=home_team["id"],
                away_team_id=away_team["id"],
                match_date=match_data["match_date"],
                season_id=season_id,
                home_score=match_data.get("home_score"),
                away_score=match_data.get("away_score"),
                match_status=match_data.get("match_status", "scheduled"),
                source="match-scraper",
                match_id=external_match_id,
                age_group_id=age_group_id_for_create,
                division_id=division_id_for_create,
                scheduled_kickoff=scheduled_kickoff,
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

    except Exception as e:
        logger.error(f"Error processing match data: {e}", exc_info=True)
        # Celery will auto-retry based on configuration
        raise
