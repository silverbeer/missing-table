"""
Match Type Data Access Object.

Handles all database operations related to match types including:
- Match type queries
- Match type reference data
"""

import structlog

from dao.base_dao import BaseDAO, dao_cache

logger = structlog.get_logger()


class MatchTypeDAO(BaseDAO):
    """Data access object for match type operations."""

    @dao_cache("match_types:all")
    def get_all_match_types(self) -> list[dict]:
        """Get all match types."""
        try:
            response = self.client.table("match_types").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying match types")
            return []

    @dao_cache("match_types:by_id:{match_type_id}")
    def get_match_type_by_id(self, match_type_id: int) -> dict | None:
        """Get match type by ID."""
        try:
            response = self.client.table("match_types").select("*").eq("id", match_type_id).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error querying match type")
            return None
