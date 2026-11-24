"""
Tournament Data Access Object.

Handles all database operations for tournaments, including:
- Tournament CRUD
- Tournament match creation (with auto-create of lightweight opponent teams)
- Public read: tournament list and detail with match results
"""

import structlog
from postgrest.exceptions import APIError

from dao.base_dao import MATCHES_READ_RELATION, BaseDAO, dao_cache, invalidates_cache
from dao.tournament_filters import (
    DEFAULT_LIMIT,
    build_filters_payload,
    empty_page,
    unavailable_filters_payload,
)

logger = structlog.get_logger()

TOURNAMENTS_CACHE_PATTERN = "mt:dao:tournaments:*"
# Tournament matches ARE matches — writing one must also bust the matches
# cache (get_match_by_id is @dao_cache under mt:dao:matches:by_id:*). Without
# this, a re-read after a tournament-score write returns the stale pre-write
# row: the SB-77 follower-notify detector sees no change and never fires, and
# even when it does the dispatcher formats the push with the stale score.
MATCHES_CACHE_PATTERN = "mt:dao:matches:*"
# Creating a lightweight opponent adds a row the cached team lists must show —
# otherwise the next Add Match still can't pick it and creates it again (SB-817).
TEAMS_CACHE_PATTERN = "mt:dao:teams:*"

# match_type_id=2 is "Tournament" (seed data)
TOURNAMENT_MATCH_TYPE_ID = 2

VALID_ROUNDS = {
    "group_stage",
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "final",
    "third_place",
    "wildcard",
    "silver_semifinal",
    "bronze_semifinal",
    "silver_final",
    "bronze_final",
    "showcase",
    "consolation",
    "placement_final",
}

# The columns of one match in a tournament's match list. Shared by the detail
# endpoint and the paged one so a row is the same shape from either (SB-1749).
TOURNAMENT_MATCH_SELECT = """
                    id,
                    match_date,
                    scheduled_kickoff,
                    match_status,
                    home_score,
                    away_score,
                    home_penalty_score,
                    away_penalty_score,
                    tournament_group,
                    tournament_round,
                    tournament_round_order,
                    age_group:age_groups!matches_age_group_id_fkey(id, name),
                    home_team:teams!matches_home_team_id_fkey(id, name, club:clubs(id, name, logo_url)),
                    away_team:teams!matches_away_team_id_fkey(id, name, club:clubs(id, name, logo_url))
                """

# PostgREST's "requested range not satisfiable": an offset past the last row
# of a counted query. For a pager that is an empty page, not a failure.
_RANGE_NOT_SATISFIABLE = "PGRST103"

# PostgREST's "could not find the function in the schema cache": the facets
# migration has not reached this database yet. The one facet failure that
# degrades to "unavailable"; anything else is a real error.
_FUNCTION_NOT_FOUND = "PGRST202"

# How long a tournament read that carries scores or match counts stays cached.
# The ingest worker cannot clear this cache: it runs without CACHE_ENABLED or
# REDIS_URL, in a different cluster from the API's Redis, so @invalidates_cache
# is a no-op there. These reads are bounded by this TTL instead, and a scraped
# score or a newly created match shows within about a minute (SB-1756).
TOURNAMENT_SCORE_CACHE_TTL = 60

# The match pages and their facets are score-bearing too. Short also keeps the
# keys of a big event expiring on their own instead of piling up for a day.
TOURNAMENT_PAGE_CACHE_TTL = TOURNAMENT_SCORE_CACHE_TTL


class TournamentDAO(BaseDAO):
    """Data access object for tournament operations."""

    # =========================================================================
    # Public read
    # =========================================================================

    def _attach_age_groups(self, tournaments: list[dict]) -> list[dict]:
        """Fetch age groups from the junction table and attach to each tournament."""
        if not tournaments:
            return tournaments
        ids = [t["id"] for t in tournaments]
        try:
            rows = (
                self.client.table("tournament_age_groups")
                .select("tournament_id, age_group:age_groups(id, name)")
                .in_("tournament_id", ids)
                .execute()
            ).data or []
        except Exception:
            logger.exception("Error fetching tournament age groups")
            rows = []

        by_tid: dict[int, list] = {t["id"]: [] for t in tournaments}
        for row in rows:
            tid = row["tournament_id"]
            if tid in by_tid:
                by_tid[tid].append(row["age_group"])

        for t in tournaments:
            t["age_groups"] = by_tid[t["id"]]
        return tournaments

    def _attach_match_counts(self, tournaments: list[dict], include_test: bool = False) -> list[dict]:
        """Fetch match counts from the matches table and attach to each tournament.

        include_test gates the SB-591 test partition, so a test fixture entered
        into a real tournament does not inflate its published match count.
        """
        if not tournaments:
            return tournaments
        for t in tournaments:
            # An exact count per tournament, asked of the database. Counting the
            # rows of one .in_() select is capped at PostgREST's 1,000-row
            # response limit, so a big tournament under-reported (SB-1752).
            try:
                count_query = (
                    self.client.table(MATCHES_READ_RELATION)
                    .select("id", count="exact", head=True)
                    .eq("tournament_id", t["id"])
                )
                if not include_test:
                    count_query = count_query.eq("is_test", False)
                # No count in the response is unknown, not zero: None, so a
                # client renders no number (SB-1767). A real 0 stays 0.
                t["match_count"] = count_query.execute().count
            except Exception:
                logger.exception("Error fetching tournament match count", tournament_id=t["id"])
                t["match_count"] = None
        return tournaments

    def _sync_age_groups(self, tournament_id: int, age_group_ids: list[int]) -> None:
        """Replace all age group links for a tournament."""
        self.client.table("tournament_age_groups").delete().eq("tournament_id", tournament_id).execute()
        if age_group_ids:
            rows = [{"tournament_id": tournament_id, "age_group_id": ag_id} for ag_id in age_group_ids]
            self.client.table("tournament_age_groups").insert(rows).execute()

    @dao_cache("tournaments:active:{include_test}:{season_id}", ttl=TOURNAMENT_SCORE_CACHE_TTL)
    def get_active_tournaments(self, include_test: bool = False, season_id: int | None = None) -> list[dict]:
        """Return all active tournaments ordered by start date descending.

        include_test gates the SB-85 test partition: real/anonymous viewers pass
        False (test tournaments hidden); admins + test users pass True.
        season_id, when provided, restricts results to that season.
        """
        try:
            query = (
                self.client.table("tournaments")
                .select("id, name, season_id, start_date, end_date, location, description, is_active, logo_url")
                .eq("is_active", True)
            )
            if not include_test:
                query = query.eq("is_test", False)
            if season_id is not None:
                query = query.eq("season_id", season_id)
            response = query.order("start_date", desc=True).execute()
            data = self._attach_age_groups(response.data or [])
            return self._attach_match_counts(data, include_test=include_test)
        except Exception:
            logger.exception("Error fetching active tournaments")
            return []

    @dao_cache("tournaments:all", ttl=TOURNAMENT_SCORE_CACHE_TTL)
    def get_all_tournaments(self) -> list[dict]:
        """Return all tournaments (admin use).

        Admin-only, so match counts deliberately include test fixtures — this is
        the view an admin uses to confirm the TSC test world exists (SB-591).
        """
        try:
            response = (
                self.client.table("tournaments")
                .select("id, name, season_id, start_date, end_date, location, description, is_active, logo_url")
                .order("start_date", desc=True)
                .execute()
            )
            data = self._attach_age_groups(response.data or [])
            return self._attach_match_counts(data, include_test=True)
        except Exception:
            logger.exception("Error fetching all tournaments")
            return []

    @dao_cache("tournaments:by_id:{tournament_id}:test{include_test}", ttl=TOURNAMENT_SCORE_CACHE_TTL)
    def get_tournament_by_id(self, tournament_id: int, include_test: bool = False) -> dict | None:
        """Return tournament with all matches for tracked teams.

        Matches are enriched with home/away team names so the frontend
        can display them without additional lookups.

        include_test gates the SB-591 test partition on the match list; it is
        part of the cache key so the two audiences never share a response.
        """
        try:
            t_response = (
                self.client.table("tournaments")
                .select("id, name, season_id, start_date, end_date, location, description, is_active, logo_url")
                .eq("id", tournament_id)
                .single()
                .execute()
            )
            if not t_response.data:
                return None

            tournament = self._attach_age_groups([t_response.data])[0]

            # Fetch matches linked to this tournament
            m_query = (
                self.client.table(MATCHES_READ_RELATION)
                .select(TOURNAMENT_MATCH_SELECT)
                .eq("tournament_id", tournament_id)
            )
            if not include_test:
                m_query = m_query.eq("is_test", False)
            m_response = m_query.order("match_date", desc=False).execute()

            tournament["matches"] = self._flatten_clubs(m_response.data or [])
            return tournament

        except Exception:
            logger.exception("Error fetching tournament by id", tournament_id=tournament_id)
            return None

    @staticmethod
    def _flatten_clubs(matches: list[dict]) -> list[dict]:
        """Lift each team's nested club to `home_team_club` / `away_team_club`.

        Matches the shape used by `/api/matches` and consumed by
        MatchDetailView / MatchesView, so the frontend club-logo code paths
        stay consistent across endpoints.
        """
        for m in matches:
            home = m.get("home_team") or {}
            away = m.get("away_team") or {}
            m["home_team_club"] = home.pop("club", None)
            m["away_team_club"] = away.pop("club", None)
        return matches

    # -------------------------------------------------------------------------
    # Paged matches and filter facets (SB-1749)
    # -------------------------------------------------------------------------

    # Default TTL: a tournament's age groups do not depend on its matches.
    @dao_cache("tournaments:age_groups:{tournament_id}")
    def get_tournament_age_groups(self, tournament_id: int) -> list[dict] | None:
        """The tournament's own age groups, or None when there is no such tournament.

        A database error is raised, not turned into None: "the lookup failed"
        must not read as "not found".
        """
        rows = self.client.table("tournaments").select("id").eq("id", tournament_id).limit(1).execute().data or []
        if not rows:
            return None
        return self._attach_age_groups(rows)[0]["age_groups"]

    def get_tournament_matches(
        self,
        tournament_id: int,
        *,
        age_group_id: int | None = None,
        group: str | None = None,
        round: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        include_test: bool = False,
    ) -> dict:
        """One page of a tournament's matches: ``{matches, total, limit, offset}``.

        Rows have the same shape as ``get_tournament_by_id``'s ``matches``.
        ``total`` is the exact number of matches the filters select, however
        many that is — it comes from the database's count, not from the page.
        Ordered by day, then kickoff, then id, so pages neither overlap nor
        skip. Raises on a database error.
        """
        filters = {
            "tournament_id": tournament_id,
            "age_group_id": age_group_id,
            "group": group,
            "round": round,
            "include_test": include_test,
        }
        # Only the pages the site itself asks for are cached: the default page
        # size at a multiple of it. Any other limit or offset is served
        # uncached, so sweeping them cannot fill the cache with keys.
        canonical = limit == DEFAULT_LIMIT and offset % DEFAULT_LIMIT == 0
        fetch = self._tournament_matches_page if canonical else self._fetch_tournament_matches_page
        page = fetch(limit=limit, offset=offset, **filters)
        if page is not None:
            return page
        if offset == 0:
            return empty_page(limit, offset)
        # Past the last row: nothing to show, but the total is still true.
        head = self._filter_tournament_matches(
            self.client.table(MATCHES_READ_RELATION).select("id", count="exact", head=True), **filters
        )
        return {**empty_page(limit, offset), "total": head.execute().count or 0}

    @staticmethod
    def _filter_tournament_matches(
        query,
        *,
        tournament_id: int,
        age_group_id: int | None,
        group: str | None,
        round: str | None,
        include_test: bool,
    ):
        """Apply the paged endpoint's filters to a matches query."""
        query = query.eq("tournament_id", tournament_id)
        if not include_test:
            query = query.eq("is_test", False)
        if age_group_id is not None:
            query = query.eq("age_group_id", age_group_id)
        if group is not None:
            query = query.eq("tournament_group", group)
        if round is not None:
            query = query.eq("tournament_round", round)
        return query

    @dao_cache(
        "tournaments:matches:{tournament_id}:age{age_group_id}:round{round}"
        ":l{limit}:o{offset}:test{include_test}:group{group}",
        ttl=TOURNAMENT_PAGE_CACHE_TTL,
    )
    def _tournament_matches_page(
        self,
        tournament_id: int,
        age_group_id: int | None,
        group: str | None,
        round: str | None,
        limit: int,
        offset: int,
        include_test: bool,
    ) -> dict | None:
        """The cached page, for canonical requests only. None when it has no rows."""
        return self._fetch_tournament_matches_page(
            tournament_id=tournament_id,
            age_group_id=age_group_id,
            group=group,
            round=round,
            limit=limit,
            offset=offset,
            include_test=include_test,
        )

    def _fetch_tournament_matches_page(
        self,
        tournament_id: int,
        age_group_id: int | None,
        group: str | None,
        round: str | None,
        limit: int,
        offset: int,
        include_test: bool,
    ) -> dict | None:
        """One page from the database. None when there are no rows on it.

        None is deliberate: ``dao_cache`` does not store it, so a caller
        guessing at group names or offsets cannot fill the cache with empty
        answers. Any other database error is raised.
        """
        try:
            response = (
                self._filter_tournament_matches(
                    self.client.table(MATCHES_READ_RELATION).select(TOURNAMENT_MATCH_SELECT, count="exact"),
                    tournament_id=tournament_id,
                    age_group_id=age_group_id,
                    group=group,
                    round=round,
                    include_test=include_test,
                )
                .order("match_date", desc=False)
                .order("scheduled_kickoff", desc=False)
                .order("id", desc=False)
                .range(offset, offset + limit - 1)
                .execute()
            )
        except APIError as exc:
            if exc.code == _RANGE_NOT_SATISFIABLE:
                return None
            logger.exception("Error fetching tournament matches page", tournament_id=tournament_id)
            raise

        rows = response.data or []
        if not rows:
            return None
        return {
            "matches": self._flatten_clubs(rows),
            "total": response.count or 0,
            "limit": limit,
            "offset": offset,
        }

    def get_tournament_filters(
        self,
        tournament_id: int,
        *,
        age_group_id: int | None = None,
        include_test: bool = False,
        on_date: str | None = None,
    ) -> dict:
        """Age groups and groups a tournament can be filtered by, with match counts.

        ``groups`` are the group-stage groups of ``age_group_id`` (of every age
        group when it is None); ``[]`` means there are none. ``on_date`` adds
        each age group's count for that day.

        The counts come from the ``tournament_filter_facets`` SQL function,
        which reaches production separately from this code. Until it exists
        the facets are reported unavailable — ``groups`` None and every
        ``matches`` None — rather than as empty lists and zeros, and the age
        groups fall back to the tournament's own. Any other database error is
        raised.
        """
        rows = self._tournament_facet_rows(
            tournament_id=tournament_id,
            age_group_id=age_group_id,
            include_test=include_test,
            on_date=on_date,
        )
        if rows is None:
            return unavailable_filters_payload(self.get_tournament_age_groups(tournament_id))
        return build_filters_payload(rows, on_date=on_date)

    # Short-lived for the same reason as the match pages: on_date and
    # age_group_id are caller-supplied, so a day-long TTL would let a visitor
    # pile up keys that every score write then has to scan.
    @dao_cache(
        "tournaments:facets:{tournament_id}:age{age_group_id}:test{include_test}:on{on_date}",
        ttl=TOURNAMENT_PAGE_CACHE_TTL,
    )
    def _tournament_facet_rows(
        self,
        tournament_id: int,
        age_group_id: int | None,
        include_test: bool,
        on_date: str | None,
    ) -> list[dict] | None:
        """Raw facet rows, or None when the SQL function does not exist yet.

        None is not cached, so the first request after the migration is applied
        gets real counts instead of a day-old "unavailable". Only the missing
        function degrades: a timeout, a revoked grant or a changed signature is
        raised, so it is seen instead of passing for "not migrated".
        """
        try:
            response = self.client.rpc(
                "tournament_filter_facets",
                {
                    "p_tournament_id": tournament_id,
                    "p_age_group_id": age_group_id,
                    "p_include_test": include_test,
                    "p_on_date": on_date,
                },
            ).execute()
            return response.data or []
        except APIError as exc:
            if exc.code == _FUNCTION_NOT_FOUND:
                logger.warning(
                    "tournament_filter_facets not found; serving filters without counts",
                    tournament_id=tournament_id,
                )
                return None
            logger.exception("Error fetching tournament filter facets", tournament_id=tournament_id)
            raise

    # =========================================================================
    # Admin write
    # =========================================================================

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def create_tournament(
        self,
        name: str,
        season_id: int,
        start_date: str,
        end_date: str | None = None,
        location: str | None = None,
        description: str | None = None,
        age_group_ids: list[int] | None = None,
        is_active: bool = True,
    ) -> dict:
        """Create a new tournament.

        Args:
            name: Tournament name (e.g. '2026 Generation adidas Cup')
            season_id: Season the tournament belongs to
            start_date: ISO date string
            end_date: ISO date string (optional)
            location: Venue/city (optional)
            description: Free text notes (optional)
            age_group_ids: Age groups for the tournament (optional)
            is_active: Controls public visibility (default True)

        Returns:
            Created tournament record with age_groups list
        """
        data = {
            "name": name,
            "season_id": season_id,
            "start_date": start_date,
            "is_active": is_active,
        }
        if end_date:
            data["end_date"] = end_date
        if location:
            data["location"] = location
        if description:
            data["description"] = description

        try:
            response = self.client.table("tournaments").insert(data).execute()
            tournament = response.data[0]
            if age_group_ids:
                self._sync_age_groups(tournament["id"], age_group_ids)
            return self._attach_age_groups([tournament])[0]
        except Exception:
            logger.exception("Error creating tournament", name=name)
            raise

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def update_tournament(
        self,
        tournament_id: int,
        name: str | None = None,
        season_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        location: str | None = None,
        description: str | None = None,
        age_group_ids: list[int] | None = None,
        is_active: bool | None = None,
        logo_url: str | None = None,
    ) -> dict | None:
        """Update tournament fields. Only provided (non-None) fields are changed.

        age_group_ids replaces all existing age group links when provided.
        """
        updates: dict = {}
        if name is not None:
            updates["name"] = name
        if season_id is not None:
            updates["season_id"] = season_id
        if start_date is not None:
            updates["start_date"] = start_date
        if end_date is not None:
            updates["end_date"] = end_date
        if location is not None:
            updates["location"] = location
        if description is not None:
            updates["description"] = description
        if is_active is not None:
            updates["is_active"] = is_active
        if logo_url is not None:
            updates["logo_url"] = logo_url

        try:
            if updates:
                self.client.table("tournaments").update(updates).eq("id", tournament_id).execute()
            if age_group_ids is not None:
                self._sync_age_groups(tournament_id, age_group_ids)
            return self.get_tournament_by_id(tournament_id)
        except Exception:
            logger.exception("Error updating tournament", tournament_id=tournament_id)
            raise

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def delete_tournament(self, tournament_id: int) -> bool:
        """Delete a tournament and cascade-nullify match links (via FK ON DELETE SET NULL)."""
        try:
            self.client.table("tournaments").delete().eq("id", tournament_id).execute()
            return True
        except Exception:
            logger.exception("Error deleting tournament", tournament_id=tournament_id)
            return False

    # =========================================================================
    # Tournament match management
    # =========================================================================

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        """Normalize a team name for comparison (trim, collapse whitespace)."""
        return " ".join(name.strip().split())

    def lookup_teams_by_name(self, name: str) -> dict:
        """Look up teams by name without creating anything.

        Returns a dict with:
          - exact: team dict if an exact (case-insensitive) match exists, else None
          - similar: list of team dicts whose names contain any word from the query
        """
        normalized = self._normalize_team_name(name)

        # Exact case-insensitive match
        exact_response = (
            self.client.table("teams")
            .select("id, name, league_id, division_id, club_id")
            .ilike("name", normalized)
            .limit(1)
            .execute()
        )
        exact = exact_response.data[0] if exact_response.data else None

        # Fall back to aliases so the combobox finds a team by any string a
        # feed uses for it — typing the long official name should surface the
        # team, not report it as new (SB-822).
        if not exact:
            alias_response = (
                self.client.table("team_aliases")
                .select("team_id")
                .ilike("external_name", normalized)
                .limit(1)
                .execute()
            )
            if alias_response.data:
                aliased = (
                    self.client.table("teams")
                    .select("id, name, league_id, division_id, club_id")
                    .eq("id", alias_response.data[0]["team_id"])
                    .limit(1)
                    .execute()
                )
                exact = aliased.data[0] if aliased.data else None

        # Similar: name contains any significant word (>= 4 chars) from query
        similar: list[dict] = []
        if not exact:
            _skip = {"city", "club", "team", "boys", "girls", "academy", "united", "soccer", "football"}
            words = [w for w in normalized.split() if len(w) >= 4 and w.lower() not in _skip]
            seen_ids: set[int] = set()
            for word in words:
                rows = (
                    self.client.table("teams")
                    .select("id, name, league_id, division_id, club_id")
                    .ilike("name", f"%{word}%")
                    .limit(5)
                    .execute()
                ).data or []
                for row in rows:
                    if row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        similar.append(row)

        return {"exact": exact, "similar": similar}

    @invalidates_cache(TEAMS_CACHE_PATTERN)
    def get_or_create_opponent_team(self, name: str, age_group_id: int) -> int:
        """Find an existing team by name or create a lightweight tournament-only team.

        Tournament opponents are created with no league, division, or club so
        they don't pollute league standings or admin team lists.

        Args:
            name: Opponent team name (e.g. 'Cedar Stars Academy')
            age_group_id: Age group for the team

        Returns:
            Team ID (existing or newly created)
        """
        normalized = self._normalize_team_name(name)

        # Exact case-insensitive match
        response = self.client.table("teams").select("id, name").ilike("name", normalized).limit(1).execute()
        if response.data:
            team_id = response.data[0]["id"]
            logger.info("Found existing team for tournament opponent", name=normalized, team_id=team_id)
            return team_id

        # Then aliases (SB-822). This check is the reason the table exists: a
        # miss here does not fail, it CREATES a team. That is how
        # 'Intercontinental Football Academy of New England' became a duplicate
        # IFA, and how a post-rename feed carrying 'Long Island Soccer Club'
        # would split that club's history.
        alias_response = (
            self.client.table("team_aliases").select("team_id").ilike("external_name", normalized).limit(1).execute()
        )
        if alias_response.data:
            team_id = alias_response.data[0]["team_id"]
            logger.info(
                "Resolved tournament opponent via alias — no team created",
                alias=normalized,
                team_id=team_id,
            )
            return team_id

        # Create lightweight team: no league, division, or club
        team_response = (
            self.client.table("teams")
            .insert(
                {
                    "name": name,
                    "city": "",
                    "academy_team": False,
                    "club_id": None,
                    "league_id": None,
                    "division_id": None,
                }
            )
            .execute()
        )
        if not team_response.data:
            raise RuntimeError(f"Failed to create opponent team: {name}")

        team_id = team_response.data[0]["id"]

        # Add age group mapping so the team can appear in age-group-filtered queries
        self.client.table("team_mappings").insert(
            {
                "team_id": team_id,
                "age_group_id": age_group_id,
                "division_id": None,
            }
        ).execute()

        logger.info("Created tournament opponent team", name=name, team_id=team_id, age_group_id=age_group_id)
        return team_id

    def _resolve_side(
        self,
        side: str,
        team_id: int | None,
        team_name: str | None,
        age_group_id: int,
    ) -> int:
        """Resolve one side of a fixture to a team id.

        A picked id wins over a name: the name may be stale text left in the
        form after the pick (SB-817).
        """
        if team_id is not None:
            return team_id
        if team_name and team_name.strip():
            return self.get_or_create_opponent_team(team_name.strip(), age_group_id)
        raise ValueError(f"Either {side}_team_id or {side}_team_name is required")

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def create_tournament_match(
        self,
        tournament_id: int,
        match_date: str,
        age_group_id: int,
        season_id: int,
        home_team_id: int | None = None,
        home_team_name: str | None = None,
        away_team_id: int | None = None,
        away_team_name: str | None = None,
        our_team_id: int | None = None,
        opponent_name: str | None = None,
        is_home: bool = True,
        home_score: int | None = None,
        away_score: int | None = None,
        home_penalty_score: int | None = None,
        away_penalty_score: int | None = None,
        match_status: str = "scheduled",
        tournament_group: str | None = None,
        tournament_round: str | None = None,
        tournament_round_order: int | None = None,
        scheduled_kickoff: str | None = None,
        opponent_team_id: int | None = None,
    ) -> dict:
        """Create a match linked to a tournament.

        Each side is either picked by id or resolved by name, and an unknown
        name creates a lightweight tournament-only team. Picking is preferred:
        name resolution matches exactly, so a typo mints a duplicate (SB-817).

        Sides are named home/away because a tournament often has no "our team"
        at all — an admin loading a bracket may track neither side (SB-819).
        The older `our_team_id` + `is_home` + `opponent_*` form still works and
        is mapped onto home/away here.

        Args:
            tournament_id: Tournament this match belongs to
            match_date: ISO date string (YYYY-MM-DD)
            age_group_id: Age group for both teams
            season_id: Season this match falls within
            home_team_id / away_team_id: existing teams chosen by the caller
            home_team_name / away_team_name: team names, created if unknown.
                Per side, give exactly one of id / name.
            our_team_id, opponent_name, opponent_team_id, is_home: deprecated
                pre-SB-819 form, mapped onto the home/away pair
            home_score / away_score: Scores (None = not yet played)
            match_status: 'scheduled', 'completed', etc.
            tournament_group: e.g. 'Group A'
            tournament_round: e.g. 'group_stage', 'quarterfinal'
            scheduled_kickoff: ISO datetime string (optional)

        Returns:
            Created match record dict
        """
        if tournament_round and tournament_round not in VALID_ROUNDS:
            raise ValueError(f"Invalid tournament_round '{tournament_round}'. Must be one of {VALID_ROUNDS}")

        # Deprecated form: map "our team + opponent" onto the home/away pair.
        if home_team_id is None and home_team_name is None and our_team_id is not None:
            if is_home:
                home_team_id = our_team_id
                away_team_id, away_team_name = opponent_team_id, opponent_name
            else:
                away_team_id = our_team_id
                home_team_id, home_team_name = opponent_team_id, opponent_name

        home_id = self._resolve_side("home", home_team_id, home_team_name, age_group_id)
        away_id = self._resolve_side("away", away_team_id, away_team_name, age_group_id)

        if home_id == away_id:
            raise ValueError("A team cannot play itself")

        home_team_id, away_team_id = home_id, away_id

        data: dict = {
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "match_date": match_date,
            "season_id": season_id,
            "age_group_id": age_group_id,
            "match_type_id": TOURNAMENT_MATCH_TYPE_ID,
            "division_id": None,
            "match_status": match_status,
            "source": "manual",
            "tournament_id": tournament_id,
        }

        if home_score is not None:
            data["home_score"] = home_score
        if away_score is not None:
            data["away_score"] = away_score
        if home_penalty_score is not None:
            data["home_penalty_score"] = home_penalty_score
        if away_penalty_score is not None:
            data["away_penalty_score"] = away_penalty_score
        if tournament_group:
            data["tournament_group"] = tournament_group
        if tournament_round:
            data["tournament_round"] = tournament_round
        if tournament_round_order is not None:
            data["tournament_round_order"] = tournament_round_order
        if scheduled_kickoff:
            data["scheduled_kickoff"] = scheduled_kickoff

        try:
            response = self.client.table("matches").insert(data).execute()
            if not response.data:
                raise RuntimeError("Match insert returned no data")
            match = response.data[0]
            logger.info(
                "Created tournament match",
                tournament_id=tournament_id,
                match_id=match["id"],
                home_team_id=home_team_id,
                away_team_id=away_team_id,
            )
            return match
        except Exception:
            logger.exception("Error creating tournament match", tournament_id=tournament_id)
            raise

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def update_tournament_match(
        self,
        match_id: int,
        home_score: int | None = None,
        away_score: int | None = None,
        home_penalty_score: int | None = None,
        away_penalty_score: int | None = None,
        match_status: str | None = None,
        tournament_group: str | None = None,
        tournament_round: str | None = None,
        tournament_round_order: int | None = None,
        scheduled_kickoff: str | None = None,
        match_date: str | None = None,
        swap_home_away: bool = False,
        home_team_id: int | None = None,
        away_team_id: int | None = None,
    ) -> dict | None:
        """Update score, status, or context fields on a tournament match.

        home_team_id / away_team_id are the resolution path for TBD
        placeholder matches: when the actual team is announced, callers
        pass the new team's id and the placeholder reference is replaced.
        Postgres enforces home_team_id <> away_team_id, so an accidental
        self-pairing aborts the write instead of silently corrupting data.
        """
        if tournament_round and tournament_round not in VALID_ROUNDS:
            raise ValueError(f"Invalid tournament_round '{tournament_round}'. Must be one of {VALID_ROUNDS}")
        if swap_home_away and (home_team_id is not None or away_team_id is not None):
            raise ValueError("swap_home_away is mutually exclusive with home_team_id / away_team_id")

        updates: dict = {}
        if home_score is not None:
            updates["home_score"] = home_score
        if away_score is not None:
            updates["away_score"] = away_score
        if home_penalty_score is not None:
            updates["home_penalty_score"] = home_penalty_score
        if away_penalty_score is not None:
            updates["away_penalty_score"] = away_penalty_score
        if match_status is not None:
            updates["match_status"] = match_status
        if tournament_group is not None:
            updates["tournament_group"] = tournament_group
        if tournament_round is not None:
            updates["tournament_round"] = tournament_round
        if tournament_round_order is not None:
            updates["tournament_round_order"] = tournament_round_order
        if scheduled_kickoff is not None:
            updates["scheduled_kickoff"] = scheduled_kickoff
        if match_date is not None:
            updates["match_date"] = match_date
        if home_team_id is not None:
            updates["home_team_id"] = home_team_id
        if away_team_id is not None:
            updates["away_team_id"] = away_team_id

        if swap_home_away:
            # Fetch current team IDs to swap them
            current = (
                self.client.table("matches").select("home_team_id, away_team_id").eq("id", match_id).single().execute()
            ).data
            if current:
                updates["home_team_id"] = current["away_team_id"]
                updates["away_team_id"] = current["home_team_id"]

        if not updates:
            return None

        try:
            response = self.client.table("matches").update(updates).eq("id", match_id).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error updating tournament match", match_id=match_id)
            raise

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN, MATCHES_CACHE_PATTERN)
    def delete_tournament_match(self, match_id: int) -> bool:
        """Remove a match from a tournament (deletes the match record entirely)."""
        try:
            self.client.table("matches").delete().eq("id", match_id).execute()
            return True
        except Exception:
            logger.exception("Error deleting tournament match", match_id=match_id)
            return False
