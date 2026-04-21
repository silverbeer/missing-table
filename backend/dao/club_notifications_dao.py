"""
Club Notification Channels Data Access Object.

Per-club destinations (Telegram chat_ids, Discord webhook URLs) used by the
live match notification dispatcher. The ``destination`` value is sensitive
and is never logged or returned in full from the API layer.
"""

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "club_notification_channels"
VALID_PLATFORMS = frozenset({"telegram", "discord"})


class ClubNotificationsDAO(BaseDAO):
    """Data access for per-club notification channel config."""

    def list_by_club(self, club_id: int) -> list[dict]:
        """Return all notification channel rows for a club (any platform, any enabled state)."""
        try:
            response = (
                self.client.table(TABLE)
                .select("*")
                .eq("club_id", club_id)
                .order("platform")
                .execute()
            )
            return response.data or []
        except Exception:
            logger.exception("dao_list_club_notifications_failed", club_id=club_id)
            return []

    def get(self, club_id: int, platform: str) -> dict | None:
        """Return the channel row for a specific (club, platform), or None."""
        try:
            response = (
                self.client.table(TABLE)
                .select("*")
                .eq("club_id", club_id)
                .eq("platform", platform)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception(
                "dao_get_club_notification_failed",
                club_id=club_id,
                platform=platform,
            )
            return None

    def upsert(
        self,
        club_id: int,
        platform: str,
        destination: str,
        enabled: bool = True,
    ) -> dict | None:
        """Create or update a channel for a (club, platform).

        Re-raises on database errors (upsert failures are not expected during
        normal use; the API layer should translate to HTTP errors).
        """
        try:
            response = (
                self.client.table(TABLE)
                .upsert(
                    {
                        "club_id": club_id,
                        "platform": platform,
                        "destination": destination,
                        "enabled": enabled,
                    },
                    on_conflict="club_id,platform",
                )
                .execute()
            )
            logger.debug(
                "dao_upsert_club_notification",
                club_id=club_id,
                platform=platform,
                enabled=enabled,
            )
            return response.data[0] if response.data else None
        except Exception:
            logger.exception(
                "dao_upsert_club_notification_failed",
                club_id=club_id,
                platform=platform,
            )
            raise

    def delete(self, club_id: int, platform: str) -> bool:
        """Remove a channel. Returns True if a row was deleted."""
        try:
            response = (
                self.client.table(TABLE)
                .delete()
                .eq("club_id", club_id)
                .eq("platform", platform)
                .execute()
            )
            deleted = bool(response.data)
            logger.debug(
                "dao_delete_club_notification",
                club_id=club_id,
                platform=platform,
                deleted=deleted,
            )
            return deleted
        except Exception:
            logger.exception(
                "dao_delete_club_notification_failed",
                club_id=club_id,
                platform=platform,
            )
            return False
