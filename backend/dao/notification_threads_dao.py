"""Which platform thread holds a match on a channel (SB-1606).

One row per (channel, match). The unique constraint is the lock: whoever
inserts the row creates the thread; anyone else reads the row and posts into
`thread_ref` once it is set. A claim whose creator died (no ref after
STALE_SECONDS) or failed (released) can be taken over, atomically.

Holds no destination. Errors are logged by type only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

TABLE = "notification_threads"
_UNIQUE_VIOLATION = "23505"
STALE_SECONDS = 120
# A released claim is backdated so it is stale at once.
_RELEASED_AT = "1970-01-01T00:00:00+00:00"


class ThreadStoreError(Exception):
    """The thread table could not be read or written. Safe to log."""


class NotificationThreadsDAO(BaseDAO):
    """Data access for match threads."""

    def claim(self, channel_id: int, match_id: int, thread_name: str) -> tuple[bool, dict]:
        """(True, row) when this caller must create the thread; (False, row) when it exists.

        Raises ThreadStoreError when the table cannot answer.
        """
        row = {"channel_id": channel_id, "match_id": match_id, "thread_name": thread_name}
        try:
            return True, self.client.table(TABLE).insert(row).execute().data[0]
        except Exception as exc:
            if _UNIQUE_VIOLATION not in str(exc):
                logger.error("dao_notification_threads_claim_failed", error_type=type(exc).__name__)
                raise ThreadStoreError("Could not claim the match thread") from None
        try:
            existing = (
                self.client.table(TABLE)
                .select("*")
                .eq("channel_id", channel_id)
                .eq("match_id", match_id)
                .limit(1)
                .execute()
                .data
            )
        except Exception as exc:
            logger.error("dao_notification_threads_read_failed", error_type=type(exc).__name__)
            raise ThreadStoreError("Could not read the match thread") from None
        if not existing:
            raise ThreadStoreError("Match thread vanished")
        return False, existing[0]

    def take_over(self, thread_id: int, now: datetime | None = None) -> dict | None:
        """Claim a thread row whose creator died or gave up. None if someone else holds it."""
        cutoff = ((now or datetime.now(UTC)) - timedelta(seconds=STALE_SECONDS)).isoformat()
        try:
            rows = (
                self.client.table(TABLE)
                .update({"created_at": (now or datetime.now(UTC)).isoformat()})
                .eq("id", thread_id)
                .is_("thread_ref", "null")
                .lt("created_at", cutoff)
                .execute()
                .data
            )
        except Exception as exc:
            logger.error("dao_notification_threads_takeover_failed", error_type=type(exc).__name__)
            raise ThreadStoreError("Could not take over the match thread") from None
        return rows[0] if rows else None

    def set_ref(self, thread_id: int, thread_ref: str) -> None:
        self._update(thread_id, {"thread_ref": thread_ref})

    def release(self, thread_id: int) -> None:
        """Give up creating the thread so the next sender can, straight away."""
        self._update(thread_id, {"created_at": _RELEASED_AT})

    def _update(self, thread_id: int, fields: dict) -> None:
        try:
            self.client.table(TABLE).update(fields).eq("id", thread_id).execute()
        except Exception as exc:
            logger.error("dao_notification_threads_update_failed", error_type=type(exc).__name__)
