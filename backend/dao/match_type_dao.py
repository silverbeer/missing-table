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
        """Get all match types, in the order competition filters should show them.

        Ordered by display_order rather than name so the UI does not have to
        know the sequence (SB-849). Alphabetical would put Flex before League
        and Friendly between them, which reads as arbitrary next to a League
        table. NULLs sort last so a type added without an order still appears.
        """
        try:
            response = (
                self.client.table("match_types")
                .select("*")
                .order("display_order", desc=False, nullsfirst=False)
                .order("name")
                .execute()
            )
            return response.data
        except Exception:
            logger.exception("Error querying match types")
            return []

    def get_match_type_by_name(self, name: str) -> dict | None:
        """Get match type by name, case-insensitively, or None.

        The feed names its competition per match ("League", "Flex") and the
        ingest path has to turn that into an id. The comparison is exact apart
        from case: a substring match would let "League" find
        "League (Pro Player Pathway)" if one were ever added and file a whole
        competition under the wrong id without a word.

        Filtered in Python over the cached full list rather than queried,
        because the table has five rows and a PostgREST `ilike` would treat a
        `%` in a feed-supplied name as a wildcard.
        """
        if not name:
            return None
        needle = name.strip().lower()
        return next((t for t in self.get_all_match_types() if (t.get("name") or "").lower() == needle), None)

    @dao_cache("match_types:by_id:{match_type_id}")
    def get_match_type_by_id(self, match_type_id: int) -> dict | None:
        """Get match type by ID."""
        try:
            response = self.client.table("match_types").select("*").eq("id", match_type_id).execute()
            return response.data[0] if response.data else None
        except Exception:
            logger.exception("Error querying match type")
            return None
