"""
Season Data Access Object.

Handles all database operations related to seasons and age groups including:
- Season CRUD operations
- Age group CRUD operations
- Current/active season queries
"""

from datetime import date

import structlog

from dao.base_dao import BaseDAO, dao_cache, invalidates_cache

logger = structlog.get_logger()

# Cache patterns for invalidation
SEASONS_CACHE_PATTERN = "mt:dao:seasons:*"
AGE_GROUPS_CACHE_PATTERN = "mt:dao:age_groups:*"


class SeasonDAO(BaseDAO):
    """Data access object for season and age group operations."""

    # === Age Group Query Methods ===

    @dao_cache("age_groups:all")
    def get_all_age_groups(self) -> list[dict]:
        """Get all age groups."""
        try:
            response = self.client.table("age_groups").select("*").order("name").execute()
            return response.data
        except Exception:
            logger.exception("Error querying age groups")
            return []

    def get_age_group_by_name(self, name: str) -> dict | None:
        """Get an age group by name (case-insensitive exact match).

        Returns the age group record (id, name).
        For match-scraper integration, this helps look up age groups by name.
        No caching - used for scraper lookups.
        """
        try:
            response = (
                self.client.table("age_groups")
                .select("id, name")
                .ilike("name", name)  # Case-insensitive match
                .limit(1)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception:
            logger.exception("Error getting age group by name", age_group_name=name)
            return None

    # === Age Group CRUD Methods ===

    @invalidates_cache(AGE_GROUPS_CACHE_PATTERN)
    def create_age_group(self, name: str) -> dict:
        """Create a new age group."""
        try:
            result = self.client.table("age_groups").insert({"name": name}).execute()
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating age group")
            raise e

    @invalidates_cache(AGE_GROUPS_CACHE_PATTERN)
    def update_age_group(self, age_group_id: int, name: str) -> dict | None:
        """Update an age group."""
        try:
            result = self.client.table("age_groups").update({"name": name}).eq("id", age_group_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating age group")
            raise e

    @invalidates_cache(AGE_GROUPS_CACHE_PATTERN)
    def delete_age_group(self, age_group_id: int) -> bool:
        """Delete an age group."""
        try:
            result = self.client.table("age_groups").delete().eq("id", age_group_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting age group")
            raise e

    # === Season Query Methods ===

    @dao_cache("seasons:all")
    def get_all_seasons(self) -> list[dict]:
        """Get all seasons."""
        try:
            response = self.client.table("seasons").select("*").order("start_date", desc=True).execute()
            return response.data
        except Exception:
            logger.exception("Error querying seasons")
            return []

    @dao_cache("seasons:current")
    def get_current_season(self) -> dict | None:
        """Get the current active season based on today's date."""
        try:
            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .lte("start_date", today)
                .gte("end_date", today)
                .single()
                .execute()
            )

            return response.data
        except Exception as e:
            logger.info("No current season found", error=str(e))
            return None

    # Cache key lives in the `matches:` namespace so it's invalidated by
    # MATCHES_CACHE_PATTERN whenever any match is created/updated/deleted.
    @dao_cache("matches:counts_by_season")
    def get_match_counts_by_season(self) -> list[dict]:
        """Return [{season_id, match_count}] for every season.

        Backs the Admin → Seasons page (SB-61). The previous client-side
        approach fetched all matches from /api/matches and filtered by
        season_id, which silently capped at Supabase's 1000-row default and
        showed bogus counts (always 1000 for the current season, 0 for
        everything older).

        One row per season; missing seasons (no matches) still appear with
        match_count=0 — the seasons list is the source of truth, the count
        is just a join.
        """
        try:
            # PostgREST embedded resource with count: one round-trip for
            # every season and its match count. Falls back to N+1 if the
            # embedded count isn't accepted.
            response = (
                self.client.table("seasons")
                .select("id, matches(count)")
                .execute()
            )
            counts = []
            for row in response.data or []:
                # `matches` comes back as a list of {count: N} when the
                # embedded count modifier is honored.
                matches_field = row.get("matches") or []
                if isinstance(matches_field, list) and matches_field:
                    match_count = matches_field[0].get("count") or 0
                else:
                    match_count = 0
                counts.append({"season_id": row["id"], "match_count": match_count})
            return counts
        except Exception:
            logger.exception("Error querying match counts by season; falling back to N+1")
            # Fallback: count per season individually. Seasons are few (<10
            # in practice), so the extra round-trips are fine.
            try:
                seasons = (
                    self.client.table("seasons").select("id").execute().data or []
                )
                counts = []
                for season in seasons:
                    sid = season["id"]
                    resp = (
                        self.client.table("matches")
                        .select("id", count="exact")
                        .eq("season_id", sid)
                        .limit(0)
                        .execute()
                    )
                    counts.append(
                        {"season_id": sid, "match_count": resp.count or 0}
                    )
                return counts
            except Exception:
                logger.exception("Error in N+1 fallback for season match counts")
                return []

    @dao_cache("seasons:active")
    def get_active_seasons(self) -> list[dict]:
        """Get active seasons (current and future) for scheduling new matches."""
        try:
            today = date.today().isoformat()

            response = (
                self.client.table("seasons")
                .select("*")
                .gte("end_date", today)
                .order("start_date", desc=False)
                .execute()
            )

            return response.data
        except Exception:
            logger.exception("Error querying active seasons")
            return []

    # === Season CRUD Methods ===

    @invalidates_cache(SEASONS_CACHE_PATTERN)
    def create_season(self, name: str, start_date: str, end_date: str) -> dict:
        """Create a new season."""
        try:
            result = (
                self.client.table("seasons")
                .insert({"name": name, "start_date": start_date, "end_date": end_date})
                .execute()
            )
            return result.data[0]
        except Exception as e:
            logger.exception("Error creating season")
            raise e

    @invalidates_cache(SEASONS_CACHE_PATTERN)
    def update_season(self, season_id: int, name: str, start_date: str, end_date: str) -> dict | None:
        """Update a season."""
        try:
            result = (
                self.client.table("seasons")
                .update({"name": name, "start_date": start_date, "end_date": end_date})
                .eq("id", season_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.exception("Error updating season")
            raise e

    @invalidates_cache(SEASONS_CACHE_PATTERN)
    def delete_season(self, season_id: int) -> bool:
        """Delete a season."""
        try:
            result = self.client.table("seasons").delete().eq("id", season_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.exception("Error deleting season")
            raise e
