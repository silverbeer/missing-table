"""
Per-club, per-platform view of notification channels.

Serves the original /api/clubs/{id}/notifications endpoints: one fan channel for
each club and platform. Rows live in `notification_channels`; when a club has
several for a platform, these methods act on the oldest.
"""

import structlog

from dao.notification_channels_dao import TABLE, NotificationChannelsDAO

logger = structlog.get_logger()


class ClubNotificationsDAO(NotificationChannelsDAO):
    """Club fan channels, addressed by (club, platform)."""

    def _club_fans(self, query, club_id: int):
        return query.eq("scope_type", "club").eq("club_id", club_id).eq("audience", "fans")

    def list_by_club(self, club_id: int) -> list[dict]:
        """Return all of a club's fan channels (any platform, any enabled state)."""
        return self._select("list_by_club", lambda q: self._club_fans(q, club_id).order("platform").order("id"))

    def get(self, club_id: int, platform: str) -> dict | None:
        """Return the oldest fan channel for a (club, platform), or None."""
        rows = self._select(
            "get",
            lambda q: self._club_fans(q, club_id).eq("platform", platform).order("id").limit(1),
        )
        return rows[0] if rows else None

    def upsert(
        self,
        club_id: int,
        platform: str,
        destination: str,
        enabled: bool = True,
        created_by: str | None = None,
    ) -> dict | None:
        """Create or update the channel for a (club, platform). Raises on database errors."""
        existing = self.get(club_id, platform)
        if existing:
            return self.update(existing["id"], {"destination": destination, "enabled": enabled})
        return self.create(
            {
                "scope_type": "club",
                "club_id": club_id,
                "audience": "fans",
                "platform": platform,
                "destination": destination,
                "enabled": enabled,
                "created_by": created_by,
            }
        )

    def set_enabled(self, club_id: int, platform: str, enabled: bool) -> dict | None:
        """Flip `enabled` on an existing channel. None when there is none."""
        existing = self.get(club_id, platform)
        if not existing:
            return None
        return self.update(existing["id"], {"enabled": enabled})

    def delete(self, club_id: int, platform: str) -> bool:
        """Remove a (club, platform) channel. Returns True if a row was deleted."""
        existing = self.get(club_id, platform)
        if existing is None:
            return False
        try:
            return self.delete_by_id(existing["id"])
        except Exception:
            logger.error("dao_delete_club_notification_failed", club_id=club_id, platform=platform)
            return False


__all__ = ["TABLE", "ClubNotificationsDAO"]
