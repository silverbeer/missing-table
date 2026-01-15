"""
League Data Access Object.

Handles all database operations related to leagues and divisions including:
- League CRUD operations
- Division CRUD operations
- League-division associations
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
LEAGUES_CACHE_PATTERN = "mt:dao:leagues:*"
DIVISIONS_CACHE_PATTERN = "mt:dao:divisions:*"


class LeagueDAO(BaseDAO):
    """Data access object for league and division operations."""

    # === League Query Methods ===

    @dao_cache("leagues:all")
    def get_all_leagues(self) -> list[dict]:
        """Get all leagues ordered by name."""
        try:
            response = self.client.table("leagues").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying leagues")
            return []

    @dao_cache("leagues:by_id:{league_id}")
    def get_league_by_id(self, league_id: int) -> dict | None:
        """Get league by ID."""
        try:
            response = (
                self.client.table("leagues")
                .select("*")
                .eq("id", league_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error querying league", league_id=league_id)
            return None

    # === League CRUD Methods ===

    @invalidates_cache(LEAGUES_CACHE_PATTERN)
    def create_league(self, league_data: dict) -> dict:
        """Create new league."""
        try:
            response = self.client.table("leagues").insert(league_data).execute()
            return response.data[0]
        except Exception:
            logger.exception("Error creating league")
            raise

    @invalidates_cache(LEAGUES_CACHE_PATTERN)
    def update_league(self, league_id: int, league_data: dict) -> dict:
        """Update league."""
        try:
            response = (
                self.client.table("leagues")
                .update(league_data)
                .eq("id", league_id)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error updating league", league_id=league_id)
            raise

    @invalidates_cache(LEAGUES_CACHE_PATTERN)
    def delete_league(self, league_id: int) -> bool:
        """Delete league (will fail if divisions exist due to FK constraint)."""
        try:
            self.client.table("leagues").delete().eq("id", league_id).execute()
            return True
        except Exception:
            logger.exception("Error deleting league", league_id=league_id)
            raise

    # === Division Query Methods ===

    @dao_cache("divisions:all")
    def get_all_divisions(self) -> list[dict]:
        """Get all divisions with league info."""
        try:
            response = (
                self.client.table("divisions")
                .select(
                    "*, leagues!divisions_league_id_fkey(id, name, description, is_active)"
                )
                .order("name")
                .execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying divisions")
            return []

    @dao_cache("divisions:by_league:{league_id}")
    def get_divisions_by_league(self, league_id: int) -> list[dict]:
        """Get divisions filtered by league."""
        try:
            response = (
                self.client.table("divisions")
                .select("*, leagues!divisions_league_id_fkey(id, name, description)")
                .eq("league_id", league_id)
                .order("name")
                .execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying divisions for league", league_id=league_id)
            return []

    def get_division_by_name(self, name: str) -> dict | None:
        """Get a division by name (case-insensitive exact match).

        Returns the division record (id, name).
        For match-scraper integration, this helps look up divisions by name.
        No caching - used for scraper lookups.
        """
        try:
            response = (
                self.client.table("divisions")
                .select("id, name")
                .ilike("name", name)  # Case-insensitive match
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception:
            logger.exception("Error getting division by name", division_name=name)
            return None

    # === Division CRUD Methods ===

    @invalidates_cache(DIVISIONS_CACHE_PATTERN)
    def create_division(self, division_data: dict) -> dict:
        """Create a new division.

        Args:
            division_data: Dict with keys: name, description (optional), league_id (required)
        """
        try:
            logger.debug("Creating division", division_data=division_data)
            result = self.client.table("divisions").insert(division_data).execute()
            logger.debug("Division created successfully", division=result.data[0])
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating division")
            raise e

    @invalidates_cache(DIVISIONS_CACHE_PATTERN)
    def update_division(self, division_id: int, division_data: dict) -> dict | None:
        """Update a division.

        Args:
            division_id: Division ID to update
            division_data: Dict with any of: name, description, league_id
        """
        try:
            result = (
                self.client.table("divisions")
                .update(division_data)
                .eq("id", division_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating division")
            raise e

    @invalidates_cache(DIVISIONS_CACHE_PATTERN)
    def delete_division(self, division_id: int) -> bool:
        """Delete a division."""
        try:
            result = self.client.table("divisions").delete().eq(
                "id", division_id
            ).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting division")
            raise e
