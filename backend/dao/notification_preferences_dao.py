"""Notification Preferences DAO (SB-57).

Per-user opt-in flags for push notification event types. Missing rows fall back
to defaults from `backend/notifications/preferences.py`.

`get_preferences_batch` is the dispatcher hot-path query — one SELECT covers
every user about to receive a given event.
"""

from __future__ import annotations

import structlog

from dao.base_dao import BaseDAO
from notifications.preferences import (
    DEFAULT_PREFERENCES,
    EVENT_TYPES,
    merge_with_defaults,
)

logger = structlog.get_logger()

TABLE = "user_notification_preferences"


class NotificationPreferencesDAO(BaseDAO):
    """Data access for user notification preferences."""

    def get_preferences(self, user_id: str) -> dict[str, bool]:
        """Return all 6 event-type flags for a user, defaults applied."""
        try:
            response = (
                self.client.table(TABLE)
                .select("event_type, enabled")
                .eq("user_id", user_id)
                .execute()
            )
            stored = {row["event_type"]: row["enabled"] for row in response.data or []}
            return merge_with_defaults(stored)
        except Exception:
            logger.exception("notification_prefs_get_failed", user_id=user_id)
            return dict(DEFAULT_PREFERENCES)

    def set_preferences(
        self, user_id: str, prefs: dict[str, bool]
    ) -> dict[str, bool]:
        """Upsert preferences for a user. Only known event types are persisted.

        Returns the resulting merged state (so the caller can echo it back to
        the client).
        """
        rows = [
            {"user_id": user_id, "event_type": event_type, "enabled": bool(enabled)}
            for event_type, enabled in prefs.items()
            if event_type in EVENT_TYPES
        ]
        if not rows:
            return self.get_preferences(user_id)
        try:
            self.client.table(TABLE).upsert(
                rows, on_conflict="user_id,event_type"
            ).execute()
        except Exception:
            logger.exception(
                "notification_prefs_set_failed",
                user_id=user_id,
                event_types=list(prefs.keys()),
            )
            # Fall through to a fresh read so the client sees current truth.
        return self.get_preferences(user_id)

    def get_preferences_batch(
        self, user_ids: list[str]
    ) -> dict[str, dict[str, bool]]:
        """Batch-fetch prefs for many users. Dispatcher hot-path.

        Returns `{user_id: {event_type: enabled, ...}}` with defaults filled in
        for any user that has no stored rows.
        """
        if not user_ids:
            return {}
        try:
            response = (
                self.client.table(TABLE)
                .select("user_id, event_type, enabled")
                .in_("user_id", user_ids)
                .execute()
            )
            stored: dict[str, dict[str, bool]] = {}
            for row in response.data or []:
                stored.setdefault(row["user_id"], {})[row["event_type"]] = row[
                    "enabled"
                ]
            return {
                uid: merge_with_defaults(stored.get(uid)) for uid in user_ids
            }
        except Exception:
            logger.exception(
                "notification_prefs_batch_failed",
                user_count=len(user_ids),
            )
            # Fallback: everyone gets defaults so we don't silently drop events.
            return {uid: dict(DEFAULT_PREFERENCES) for uid in user_ids}
