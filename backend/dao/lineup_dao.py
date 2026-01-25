"""
Lineup Data Access Object.

Handles all database operations for match lineups/formations:
- Get lineup for a team in a match
- Save/update lineup (upsert)
"""

import structlog

from dao.base_dao import BaseDAO, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
LINEUP_CACHE_PATTERN = "mt:dao:lineup:*"


class LineupDAO(BaseDAO):
    """Data access object for match lineup operations."""

    def get_lineup(self, match_id: int, team_id: int) -> dict | None:
        """
        Get lineup for a team in a specific match.

        Args:
            match_id: Match ID
            team_id: Team ID

        Returns:
            Lineup dict with enriched player details or None if not found
        """
        try:
            response = (
                self.client.table("match_lineups")
                .select("*")
                .eq("match_id", match_id)
                .eq("team_id", team_id)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return None

            lineup = response.data[0]

            # Enrich positions with player details
            positions = lineup.get("positions", [])
            if positions:
                player_ids = [p.get("player_id") for p in positions if p.get("player_id")]
                if player_ids:
                    players_response = (
                        self.client.table("players")
                        .select("id, jersey_number, first_name, last_name")
                        .in_("id", player_ids)
                        .execute()
                    )
                    players_map = {p["id"]: p for p in (players_response.data or [])}

                    # Enrich each position with player info
                    for pos in positions:
                        player_id = pos.get("player_id")
                        if player_id and player_id in players_map:
                            player = players_map[player_id]
                            pos["jersey_number"] = player.get("jersey_number")
                            pos["first_name"] = player.get("first_name")
                            pos["last_name"] = player.get("last_name")
                            first = player.get("first_name", "")
                            last = player.get("last_name", "")
                            pos["display_name"] = f"{first} {last}".strip()

                    lineup["positions"] = positions

            return lineup

        except Exception as e:
            logger.error("lineup_get_error", match_id=match_id, team_id=team_id, error=str(e))
            return None

    @invalidates_cache(LINEUP_CACHE_PATTERN)
    def save_lineup(
        self,
        match_id: int,
        team_id: int,
        formation_name: str,
        positions: list[dict],
        user_id: str | None = None,
    ) -> dict | None:
        """
        Save or update lineup for a team in a match (upsert).

        Args:
            match_id: Match ID
            team_id: Team ID
            formation_name: Formation name (e.g., "4-3-3")
            positions: List of {player_id, position} dicts
            user_id: ID of user making the change

        Returns:
            Saved lineup dict
        """
        try:
            # Check if lineup exists
            existing = (
                self.client.table("match_lineups")
                .select("id")
                .eq("match_id", match_id)
                .eq("team_id", team_id)
                .execute()
            )

            lineup_data = {
                "match_id": match_id,
                "team_id": team_id,
                "formation_name": formation_name,
                "positions": positions,
            }

            if existing.data and len(existing.data) > 0:
                # Update existing
                lineup_data["updated_by"] = user_id
                response = (
                    self.client.table("match_lineups")
                    .update(lineup_data)
                    .eq("match_id", match_id)
                    .eq("team_id", team_id)
                    .execute()
                )
            else:
                # Insert new
                lineup_data["created_by"] = user_id
                lineup_data["updated_by"] = user_id
                response = self.client.table("match_lineups").insert(lineup_data).execute()

            if response.data and len(response.data) > 0:
                logger.info(
                    "lineup_saved",
                    match_id=match_id,
                    team_id=team_id,
                    formation=formation_name,
                    player_count=len(positions),
                )
                return response.data[0]
            return None

        except Exception as e:
            logger.error(
                "lineup_save_error",
                match_id=match_id,
                team_id=team_id,
                error=str(e),
            )
            return None

    def get_lineups_for_match(self, match_id: int) -> dict:
        """
        Get lineups for both teams in a match.

        Args:
            match_id: Match ID

        Returns:
            Dict with 'home' and 'away' keys containing lineups (or None)
        """
        try:
            response = (
                self.client.table("match_lineups")
                .select("*")
                .eq("match_id", match_id)
                .execute()
            )

            # Get match to determine home/away team IDs
            match_response = (
                self.client.table("matches")
                .select("home_team_id, away_team_id")
                .eq("id", match_id)
                .execute()
            )

            result = {"home": None, "away": None}

            if not match_response.data:
                return result

            match = match_response.data[0]
            home_team_id = match.get("home_team_id")
            away_team_id = match.get("away_team_id")

            for lineup in (response.data or []):
                team_id = lineup.get("team_id")
                if team_id == home_team_id:
                    result["home"] = lineup
                elif team_id == away_team_id:
                    result["away"] = lineup

            return result

        except Exception as e:
            logger.error("lineup_get_match_error", match_id=match_id, error=str(e))
            return {"home": None, "away": None}
