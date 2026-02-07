"""
Player Stats Data Access Object.

Handles all database operations for player statistics:
- Per-match stats (player_match_stats table)
- Season aggregations
- Goal increment/decrement for live game
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
STATS_CACHE_PATTERN = "mt:dao:stats:*"


class PlayerStatsDAO(BaseDAO):
    """Data access object for player statistics operations."""

    # === Read Operations ===

    def get_match_stats(self, player_id: int, match_id: int) -> dict | None:
        """
        Get stats for a player in a specific match.

        Args:
            player_id: Player ID
            match_id: Match ID

        Returns:
            Stats dict or None if not found
        """
        try:
            response = (
                self.client.table("player_match_stats")
                .select("*")
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_get_match_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    @invalidates_cache(STATS_CACHE_PATTERN)
    def get_or_create_match_stats(self, player_id: int, match_id: int) -> dict | None:
        """
        Get or create stats record for a player in a match.

        Used when recording stats - ensures a record exists.

        Args:
            player_id: Player ID
            match_id: Match ID

        Returns:
            Stats dict (existing or newly created)
        """
        try:
            # Try to get existing
            existing = self.get_match_stats(player_id, match_id)
            if existing:
                return existing

            # Create new record with defaults
            response = (
                self.client.table("player_match_stats")
                .insert(
                    {
                        "player_id": player_id,
                        "match_id": match_id,
                        "started": False,
                        "minutes_played": 0,
                        "goals": 0,
                    }
                )
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info("stats_record_created", player_id=player_id, match_id=match_id)
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_get_or_create_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    @dao_cache("stats:player:{player_id}:season:{season_id}")
    def get_player_season_stats(self, player_id: int, season_id: int) -> dict | None:
        """
        Get aggregated stats for a player across a season.

        Args:
            player_id: Player ID
            season_id: Season ID

        Returns:
            Aggregated stats dict with games_played, games_started,
            total_minutes, total_goals
        """
        try:
            # Get all match stats for this player where match is in the season
            # Need to join with matches to filter by season
            response = (
                self.client.table("player_match_stats")
                .select("""
                *,
                match:matches!inner(id, season_id)
            """)
                .eq("player_id", player_id)
                .eq("match.season_id", season_id)
                .execute()
            )

            stats = response.data or []

            # Aggregate
            games_played = len(stats)
            games_started = sum(1 for s in stats if s.get("started"))
            total_minutes = sum(s.get("minutes_played", 0) for s in stats)
            total_goals = sum(s.get("goals", 0) for s in stats)

            return {
                "player_id": player_id,
                "season_id": season_id,
                "games_played": games_played,
                "games_started": games_started,
                "total_minutes": total_minutes,
                "total_goals": total_goals,
            }

        except Exception as e:
            logger.error("stats_season_error", player_id=player_id, season_id=season_id, error=str(e))
            return None

    @dao_cache("stats:team:{team_id}:season:{season_id}")
    def get_team_stats(self, team_id: int, season_id: int) -> list[dict]:
        """
        Get aggregated stats for all players on a team for a season.

        Args:
            team_id: Team ID
            season_id: Season ID

        Returns:
            List of player stats dicts sorted by goals (descending)
        """
        try:
            # First get all players on this team/season
            players_response = (
                self.client.table("players")
                .select("id, jersey_number, first_name, last_name")
                .eq("team_id", team_id)
                .eq("season_id", season_id)
                .eq("is_active", True)
                .execute()
            )

            players = players_response.data or []

            result = []
            for player in players:
                # Get season stats for each player
                stats = self.get_player_season_stats(player["id"], season_id)
                if stats:
                    result.append(
                        {
                            "player_id": player["id"],
                            "jersey_number": player["jersey_number"],
                            "first_name": player.get("first_name"),
                            "last_name": player.get("last_name"),
                            "games_played": stats["games_played"],
                            "games_started": stats["games_started"],
                            "total_minutes": stats["total_minutes"],
                            "total_goals": stats["total_goals"],
                        }
                    )

            # Sort by goals descending
            result.sort(key=lambda x: x["total_goals"], reverse=True)
            return result

        except Exception as e:
            logger.error("stats_team_error", team_id=team_id, season_id=season_id, error=str(e))
            return []

    @dao_cache("stats:leaderboard:goals:s{season_id}:l{league_id}:d{division_id}:a{age_group_id}:mt{match_type_id}:lim{limit}")
    def get_goals_leaderboard(
        self,
        season_id: int,
        league_id: int | None = None,
        division_id: int | None = None,
        age_group_id: int | None = None,
        match_type_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get top goal scorers filtered by league/division/age group/match type.

        Args:
            season_id: Season ID (required)
            league_id: Optional league filter
            division_id: Optional division filter
            age_group_id: Optional age group filter
            match_type_id: Optional match type filter (e.g. 4 for Playoff)
            limit: Maximum results (default 50)

        Returns:
            List of player dicts with goals stats, ranked by goals descending
        """
        try:
            # Build the query using Supabase RPC or raw SQL
            # Since Supabase Python SDK doesn't support complex aggregations well,
            # we'll fetch the data and aggregate in Python

            # Get all player match stats for matches in this season
            query = (
                self.client.table("player_match_stats")
                .select("""
                    player_id,
                    goals,
                    match:matches!inner(
                        id,
                        season_id,
                        match_status,
                        match_type_id,
                        division_id,
                        age_group_id,
                        division:divisions(
                            id,
                            league_id
                        )
                    ),
                    player:players!inner(
                        id,
                        jersey_number,
                        first_name,
                        last_name,
                        team_id,
                        team:teams(
                            id,
                            name
                        )
                    )
                """)
                .eq("match.season_id", season_id)
            )

            # Apply optional filters
            if division_id is not None:
                query = query.eq("match.division_id", division_id)
            if age_group_id is not None:
                query = query.eq("match.age_group_id", age_group_id)

            response = query.execute()
            stats = response.data or []

            # Filter in Python since PostgREST nested filters on !inner joins are unreliable
            # Include completed and forfeit matches (forfeit matches can have real goals)
            stats = [
                s for s in stats
                if s.get("match", {}).get("match_status") in ("completed", "forfeit")
            ]
            if match_type_id is not None:
                stats = [
                    s for s in stats
                    if s.get("match", {}).get("match_type_id") == match_type_id
                ]
            if league_id is not None:
                # For matches with a division, check division.league_id directly.
                # For playoff matches (division_id is null), check if the player's
                # team plays in this league by looking at their divisional matches.
                league_team_ids = self._get_league_team_ids(league_id, season_id)
                stats = [
                    s for s in stats
                    if (s.get("match", {}).get("division") or {}).get("league_id") == league_id
                    or (
                        s.get("match", {}).get("division") is None
                        and s.get("player", {}).get("team_id") in league_team_ids
                    )
                ]

            # Aggregate by player
            player_goals: dict[int, dict] = {}
            for stat in stats:
                player = stat.get("player")
                if not player:
                    continue

                player_id = player["id"]
                goals = stat.get("goals", 0)

                if player_id not in player_goals:
                    team = player.get("team", {}) or {}
                    player_goals[player_id] = {
                        "player_id": player_id,
                        "jersey_number": player.get("jersey_number"),
                        "first_name": player.get("first_name"),
                        "last_name": player.get("last_name"),
                        "team_id": player.get("team_id"),
                        "team_name": team.get("name"),
                        "goals": 0,
                        "games_played": 0,
                    }

                player_goals[player_id]["goals"] += goals
                player_goals[player_id]["games_played"] += 1

            # Filter out players with 0 goals and sort
            result = [p for p in player_goals.values() if p["goals"] > 0]
            result.sort(key=lambda x: (-x["goals"], x["games_played"]))

            # Calculate goals per game and add rank
            for i, player in enumerate(result[:limit], start=1):
                player["rank"] = i
                games = player["games_played"]
                player["goals_per_game"] = round(player["goals"] / games, 2) if games > 0 else 0.0

            return result[:limit]

        except Exception:
            logger.exception(
                "stats_goals_leaderboard_error",
                season_id=season_id,
                league_id=league_id,
                division_id=division_id,
                age_group_id=age_group_id,
                match_type_id=match_type_id,
            )
            raise

    def _get_league_team_ids(self, league_id: int, season_id: int) -> set[int]:
        """Get team IDs that participate in a league via their divisional matches.

        Used to attribute playoff goals (which have no division) to the correct league.
        """
        try:
            # Get divisions belonging to this league
            div_response = (
                self.client.table("divisions")
                .select("id")
                .eq("league_id", league_id)
                .execute()
            )
            division_ids = [d["id"] for d in (div_response.data or [])]
            if not division_ids:
                return set()

            # Get teams that have matches in those divisions for this season
            matches_response = (
                self.client.table("matches")
                .select("home_team_id, away_team_id")
                .eq("season_id", season_id)
                .in_("division_id", division_ids)
                .execute()
            )
            team_ids = set()
            for m in matches_response.data or []:
                team_ids.add(m["home_team_id"])
                team_ids.add(m["away_team_id"])
            return team_ids

        except Exception:
            logger.exception("stats_get_league_team_ids_error", league_id=league_id)
            return set()

    def get_team_match_stats(self, match_id: int, team_id: int) -> list[dict]:
        """
        Get player stats for a specific team in a match, joined with player info.

        Args:
            match_id: Match ID
            team_id: Team ID

        Returns:
            List of player stats dicts with player details
        """
        try:
            # Get all players on this team for the match's season
            # First get the match to find the season
            match_response = (
                self.client.table("matches")
                .select("season_id")
                .eq("id", match_id)
                .single()
                .execute()
            )
            if not match_response.data:
                return []

            season_id = match_response.data["season_id"]

            # Get all players on the team for this season
            players_response = (
                self.client.table("players")
                .select("id, jersey_number, first_name, last_name")
                .eq("team_id", team_id)
                .eq("season_id", season_id)
                .eq("is_active", True)
                .order("jersey_number")
                .execute()
            )

            players = players_response.data or []

            # Get existing stats for these players in this match
            player_ids = [p["id"] for p in players]
            if not player_ids:
                return []

            stats_response = (
                self.client.table("player_match_stats")
                .select("*")
                .eq("match_id", match_id)
                .in_("player_id", player_ids)
                .execute()
            )

            stats_by_player = {s["player_id"]: s for s in (stats_response.data or [])}

            # Merge player info with stats
            result = []
            for player in players:
                stats = stats_by_player.get(player["id"], {})
                result.append({
                    "player_id": player["id"],
                    "jersey_number": player["jersey_number"],
                    "first_name": player.get("first_name"),
                    "last_name": player.get("last_name"),
                    "started": stats.get("started", False),
                    "minutes_played": stats.get("minutes_played", 0),
                    "goals": stats.get("goals", 0),
                })

            return result

        except Exception as e:
            logger.error(
                "stats_team_match_error",
                match_id=match_id,
                team_id=team_id,
                error=str(e),
            )
            return []

    @invalidates_cache(STATS_CACHE_PATTERN)
    def batch_update_stats(self, match_id: int, player_stats: list[dict]) -> bool:
        """
        Batch upsert started/minutes_played for multiple players in a match.

        Args:
            match_id: Match ID
            player_stats: List of dicts with player_id, started, minutes_played

        Returns:
            True if successful
        """
        try:
            for entry in player_stats:
                player_id = entry["player_id"]
                # Ensure record exists
                self.get_or_create_match_stats(player_id, match_id)

                # Update started and minutes
                self.client.table("player_match_stats").update({
                    "started": entry["started"],
                    "minutes_played": entry["minutes_played"],
                }).eq("player_id", player_id).eq("match_id", match_id).execute()

            logger.info(
                "stats_batch_updated",
                match_id=match_id,
                player_count=len(player_stats),
            )
            return True

        except Exception as e:
            logger.error(
                "stats_batch_update_error",
                match_id=match_id,
                error=str(e),
            )
            return False

    # === Update Operations ===

    @invalidates_cache(STATS_CACHE_PATTERN)
    def increment_goals(self, player_id: int, match_id: int) -> dict | None:
        """
        Increment goal count for a player in a match.

        Creates stats record if it doesn't exist.

        Args:
            player_id: Player ID
            match_id: Match ID

        Returns:
            Updated stats dict
        """
        try:
            # Ensure record exists
            stats = self.get_or_create_match_stats(player_id, match_id)
            if not stats:
                return None

            current_goals = stats.get("goals", 0)

            response = (
                self.client.table("player_match_stats")
                .update({"goals": current_goals + 1})
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info(
                    "stats_goal_incremented",
                    player_id=player_id,
                    match_id=match_id,
                    new_total=current_goals + 1,
                )
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_increment_goals_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    @invalidates_cache(STATS_CACHE_PATTERN)
    def decrement_goals(self, player_id: int, match_id: int) -> dict | None:
        """
        Decrement goal count for a player in a match.

        Won't go below 0.

        Args:
            player_id: Player ID
            match_id: Match ID

        Returns:
            Updated stats dict
        """
        try:
            stats = self.get_match_stats(player_id, match_id)
            if not stats:
                return None

            current_goals = stats.get("goals", 0)
            new_goals = max(0, current_goals - 1)

            response = (
                self.client.table("player_match_stats")
                .update({"goals": new_goals})
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info(
                    "stats_goal_decremented",
                    player_id=player_id,
                    match_id=match_id,
                    new_total=new_goals,
                )
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_decrement_goals_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    @invalidates_cache(STATS_CACHE_PATTERN)
    def set_started(self, player_id: int, match_id: int, started: bool) -> dict | None:
        """
        Set whether a player started a match.

        Args:
            player_id: Player ID
            match_id: Match ID
            started: True if player started

        Returns:
            Updated stats dict
        """
        try:
            # Ensure record exists
            self.get_or_create_match_stats(player_id, match_id)

            response = (
                self.client.table("player_match_stats")
                .update({"started": started})
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info("stats_started_updated", player_id=player_id, match_id=match_id, started=started)
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_set_started_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    @invalidates_cache(STATS_CACHE_PATTERN)
    def update_minutes(self, player_id: int, match_id: int, minutes: int) -> dict | None:
        """
        Update minutes played for a player in a match.

        Args:
            player_id: Player ID
            match_id: Match ID
            minutes: Minutes played

        Returns:
            Updated stats dict
        """
        try:
            # Ensure record exists
            self.get_or_create_match_stats(player_id, match_id)

            response = (
                self.client.table("player_match_stats")
                .update({"minutes_played": minutes})
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info("stats_minutes_updated", player_id=player_id, match_id=match_id, minutes=minutes)
                return response.data[0]
            return None

        except Exception as e:
            logger.error("stats_update_minutes_error", player_id=player_id, match_id=match_id, error=str(e))
            return None

    # === Batch Operations ===

    @invalidates_cache(STATS_CACHE_PATTERN)
    def record_match_appearance(
        self, player_id: int, match_id: int, started: bool = False, minutes: int = 0
    ) -> dict | None:
        """
        Record a player's appearance in a match.

        Convenience method to set started and minutes at once.

        Args:
            player_id: Player ID
            match_id: Match ID
            started: Whether player started
            minutes: Minutes played

        Returns:
            Updated stats dict
        """
        try:
            # Ensure record exists
            self.get_or_create_match_stats(player_id, match_id)

            response = (
                self.client.table("player_match_stats")
                .update({"started": started, "minutes_played": minutes})
                .eq("player_id", player_id)
                .eq("match_id", match_id)
                .execute()
            )

            if response.data and len(response.data) > 0:
                logger.info(
                    "stats_appearance_recorded",
                    player_id=player_id,
                    match_id=match_id,
                    started=started,
                    minutes=minutes,
                )
                return response.data[0]
            return None

        except Exception as e:
            logger.error(
                "stats_record_appearance_error",
                player_id=player_id,
                match_id=match_id,
                error=str(e),
            )
            return None
