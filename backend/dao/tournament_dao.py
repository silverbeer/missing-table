"""
Tournament Data Access Object.

Handles all database operations for tournaments, including:
- Tournament CRUD
- Tournament match creation (with auto-create of lightweight opponent teams)
- Public read: tournament list and detail with match results
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

TOURNAMENTS_CACHE_PATTERN = "mt:dao:tournaments:*"

# match_type_id=2 is "Tournament" (seed data)
TOURNAMENT_MATCH_TYPE_ID = 2

VALID_ROUNDS = {"group_stage", "round_of_16", "quarterfinal", "semifinal", "final", "third_place"}


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

    def _attach_match_counts(self, tournaments: list[dict]) -> list[dict]:
        """Fetch match counts from the matches table and attach to each tournament."""
        if not tournaments:
            return tournaments
        ids = [t["id"] for t in tournaments]
        try:
            rows = (
                self.client.table("matches")
                .select("tournament_id")
                .in_("tournament_id", ids)
                .execute()
            ).data or []
        except Exception:
            logger.exception("Error fetching tournament match counts")
            rows = []
        counts: dict[int, int] = {t["id"]: 0 for t in tournaments}
        for row in rows:
            tid = row.get("tournament_id")
            if tid in counts:
                counts[tid] += 1
        for t in tournaments:
            t["match_count"] = counts[t["id"]]
        return tournaments

    def _sync_age_groups(self, tournament_id: int, age_group_ids: list[int]) -> None:
        """Replace all age group links for a tournament."""
        self.client.table("tournament_age_groups").delete().eq("tournament_id", tournament_id).execute()
        if age_group_ids:
            rows = [{"tournament_id": tournament_id, "age_group_id": ag_id} for ag_id in age_group_ids]
            self.client.table("tournament_age_groups").insert(rows).execute()

    @dao_cache("tournaments:active")
    def get_active_tournaments(self) -> list[dict]:
        """Return all active tournaments ordered by start date descending."""
        try:
            response = (
                self.client.table("tournaments")
                .select("id, name, start_date, end_date, location, description, is_active")
                .eq("is_active", True)
                .order("start_date", desc=True)
                .execute()
            )
            data = self._attach_age_groups(response.data or [])
            return self._attach_match_counts(data)
        except Exception:
            logger.exception("Error fetching active tournaments")
            return []

    @dao_cache("tournaments:all")
    def get_all_tournaments(self) -> list[dict]:
        """Return all tournaments (admin use)."""
        try:
            response = (
                self.client.table("tournaments")
                .select("id, name, start_date, end_date, location, description, is_active")
                .order("start_date", desc=True)
                .execute()
            )
            data = self._attach_age_groups(response.data or [])
            return self._attach_match_counts(data)
        except Exception:
            logger.exception("Error fetching all tournaments")
            return []

    @dao_cache("tournaments:by_id:{tournament_id}")
    def get_tournament_by_id(self, tournament_id: int) -> dict | None:
        """Return tournament with all matches for tracked teams.

        Matches are enriched with home/away team names so the frontend
        can display them without additional lookups.
        """
        try:
            t_response = (
                self.client.table("tournaments")
                .select("id, name, start_date, end_date, location, description, is_active")
                .eq("id", tournament_id)
                .single()
                .execute()
            )
            if not t_response.data:
                return None

            tournament = self._attach_age_groups([t_response.data])[0]

            # Fetch matches linked to this tournament
            m_response = (
                self.client.table("matches")
                .select("""
                    id,
                    match_date,
                    scheduled_kickoff,
                    match_status,
                    home_score,
                    away_score,
                    tournament_group,
                    tournament_round,
                    home_team:teams!matches_home_team_id_fkey(id, name),
                    away_team:teams!matches_away_team_id_fkey(id, name)
                """)
                .eq("tournament_id", tournament_id)
                .order("match_date", desc=False)
                .execute()
            )

            tournament["matches"] = m_response.data or []
            return tournament

        except Exception:
            logger.exception("Error fetching tournament by id", tournament_id=tournament_id)
            return None

    # =========================================================================
    # Admin write
    # =========================================================================

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def create_tournament(
        self,
        name: str,
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
        start_date: str | None = None,
        end_date: str | None = None,
        location: str | None = None,
        description: str | None = None,
        age_group_ids: list[int] | None = None,
        is_active: bool | None = None,
    ) -> dict | None:
        """Update tournament fields. Only provided (non-None) fields are changed.

        age_group_ids replaces all existing age group links when provided.
        """
        updates: dict = {}
        if name is not None:
            updates["name"] = name
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
        # Look for existing team with this exact name (case-insensitive)
        response = (
            self.client.table("teams")
            .select("id, name")
            .ilike("name", name)
            .limit(1)
            .execute()
        )
        if response.data:
            team_id = response.data[0]["id"]
            logger.info("Found existing team for tournament opponent", name=name, team_id=team_id)
            return team_id

        # Create lightweight team: no league, division, or club
        team_response = (
            self.client.table("teams")
            .insert({
                "name": name,
                "city": "",
                "academy_team": False,
                "club_id": None,
                "league_id": None,
                "division_id": None,
            })
            .execute()
        )
        if not team_response.data:
            raise RuntimeError(f"Failed to create opponent team: {name}")

        team_id = team_response.data[0]["id"]

        # Add age group mapping so the team can appear in age-group-filtered queries
        self.client.table("team_mappings").insert({
            "team_id": team_id,
            "age_group_id": age_group_id,
            "division_id": None,
        }).execute()

        logger.info("Created tournament opponent team", name=name, team_id=team_id, age_group_id=age_group_id)
        return team_id

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def create_tournament_match(
        self,
        tournament_id: int,
        our_team_id: int,
        opponent_name: str,
        match_date: str,
        age_group_id: int,
        season_id: int,
        is_home: bool = True,
        home_score: int | None = None,
        away_score: int | None = None,
        match_status: str = "scheduled",
        tournament_group: str | None = None,
        tournament_round: str | None = None,
        scheduled_kickoff: str | None = None,
    ) -> dict:
        """Create a match linked to a tournament.

        The opponent team is resolved by name — created automatically if not
        already in the database.

        Args:
            tournament_id: Tournament this match belongs to
            our_team_id: ID of the tracked team (IFA, Cedar Stars, etc.)
            opponent_name: Opponent's name as plain text
            match_date: ISO date string (YYYY-MM-DD)
            age_group_id: Age group for both teams
            season_id: Season this match falls within
            is_home: True if our_team_id is the home team
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

        opponent_id = self.get_or_create_opponent_team(opponent_name, age_group_id)

        home_team_id = our_team_id if is_home else opponent_id
        away_team_id = opponent_id if is_home else our_team_id

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
        if tournament_group:
            data["tournament_group"] = tournament_group
        if tournament_round:
            data["tournament_round"] = tournament_round
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

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def update_tournament_match(
        self,
        match_id: int,
        home_score: int | None = None,
        away_score: int | None = None,
        match_status: str | None = None,
        tournament_group: str | None = None,
        tournament_round: str | None = None,
        scheduled_kickoff: str | None = None,
        match_date: str | None = None,
        swap_home_away: bool = False,
    ) -> dict | None:
        """Update score, status, or context fields on a tournament match."""
        if tournament_round and tournament_round not in VALID_ROUNDS:
            raise ValueError(f"Invalid tournament_round '{tournament_round}'. Must be one of {VALID_ROUNDS}")

        updates: dict = {}
        if home_score is not None:
            updates["home_score"] = home_score
        if away_score is not None:
            updates["away_score"] = away_score
        if match_status is not None:
            updates["match_status"] = match_status
        if tournament_group is not None:
            updates["tournament_group"] = tournament_group
        if tournament_round is not None:
            updates["tournament_round"] = tournament_round
        if scheduled_kickoff is not None:
            updates["scheduled_kickoff"] = scheduled_kickoff
        if match_date is not None:
            updates["match_date"] = match_date

        if swap_home_away:
            # Fetch current team IDs to swap them
            current = (
                self.client.table("matches")
                .select("home_team_id, away_team_id")
                .eq("id", match_id)
                .single()
                .execute()
            ).data
            if current:
                updates["home_team_id"] = current["away_team_id"]
                updates["away_team_id"] = current["home_team_id"]

        if not updates:
            return None

        try:
            response = (
                self.client.table("matches")
                .update(updates)
                .eq("id", match_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error updating tournament match", match_id=match_id)
            raise

    @invalidates_cache(TOURNAMENTS_CACHE_PATTERN)
    def delete_tournament_match(self, match_id: int) -> bool:
        """Remove a match from a tournament (deletes the match record entirely)."""
        try:
            self.client.table("matches").delete().eq("id", match_id).execute()
            return True
        except Exception:
            logger.exception("Error deleting tournament match", match_id=match_id)
            return False
