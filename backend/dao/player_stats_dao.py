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

    @dao_cache("stats:leaderboard:goals:s{season_id}:l{league_id}:d{division_id}:a{age_group_id}:lim{limit}")
    def get_goals_leaderboard(
        self,
        season_id: int,
        league_id: int | None = None,
        division_id: int | None = None,
        age_group_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get top goal scorers filtered by league/division/age group.

        Args:
            season_id: Season ID (required)
            league_id: Optional league filter
            division_id: Optional division filter
            age_group_id: Optional age group filter
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
                .eq("match.match_status", "completed")
            )

            # Apply optional filters
            if division_id is not None:
                query = query.eq("match.division_id", division_id)
            if age_group_id is not None:
                query = query.eq("match.age_group_id", age_group_id)

            response = query.execute()
            stats = response.data or []

            # Filter by league_id if specified (need to do this in Python since nested filter)
            if league_id is not None:
                stats = [
                    s for s in stats
                    if s.get("match", {}).get("division", {}).get("league_id") == league_id
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

        except Exception as e:
            logger.error(
                "stats_goals_leaderboard_error",
                season_id=season_id,
                league_id=league_id,
                division_id=division_id,
                age_group_id=age_group_id,
                error=str(e),
            )
            return []

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
