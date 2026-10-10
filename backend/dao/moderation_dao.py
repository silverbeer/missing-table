"""Moderation DAO for live match chat (SB-1309).

Three things App Store guideline 1.2 asks of user-generated content, beyond
the word filter in services/content_filter.py:

- **Report** — content_reports, one row per (message, reporter). The message
  text, author and match are copied onto the row because chat messages are
  hard-deleted when they expire.
- **Block** — user_blocks. The read endpoints drop a blocked author's events
  for the blocker.
- **Eject** — user_profiles.chat_banned_at. A banned user cannot post.

All three tables are service-key only (RLS on, no client grants), so every
access goes through here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from dao.base_dao import BaseDAO

logger = structlog.get_logger()

REPORTS = "content_reports"
BLOCKS = "user_blocks"

# Postgres unique_violation: a repeated report or block is not an error.
_UNIQUE_VIOLATION = "23505"
# Postgres foreign_key_violation: the user being blocked does not exist.
_FOREIGN_KEY_VIOLATION = "23503"


class UnknownUserError(Exception):
    """The user being blocked has no profile."""


def _is_pg_error(exc: Exception, code: str) -> bool:
    return getattr(exc, "code", None) == code or code in str(exc)


class ModerationDAO(BaseDAO):
    """Data access for chat reports, blocks and bans."""

    # ------------------------------------------------------------------
    # Blocks
    # ------------------------------------------------------------------

    def block_user(self, blocker_id: str, blocked_id: str) -> None:
        """Block `blocked_id` for `blocker_id`. Idempotent.

        Raises UnknownUserError when `blocked_id` has no profile.
        """
        try:
            self.client.table(BLOCKS).insert({"blocker_id": blocker_id, "blocked_id": blocked_id}).execute()
        except Exception as exc:
            if _is_pg_error(exc, _UNIQUE_VIOLATION):
                return
            if _is_pg_error(exc, _FOREIGN_KEY_VIOLATION):
                raise UnknownUserError(blocked_id) from exc
            raise
        logger.info("user_blocked", blocker_id=blocker_id, blocked_id=blocked_id)

    def unblock_user(self, blocker_id: str, blocked_id: str) -> None:
        """Remove a block. Idempotent: no row is not an error."""
        self.client.table(BLOCKS).delete().eq("blocker_id", blocker_id).eq("blocked_id", blocked_id).execute()
        logger.info("user_unblocked", blocker_id=blocker_id, blocked_id=blocked_id)

    def list_blocks(self, blocker_id: str) -> list[dict]:
        """The users `blocker_id` has blocked, newest first, with usernames.

        A blocked user whose profile is gone keeps its row (the FK cascades,
        so in practice it cannot) and reports username None.
        """
        rows = (
            self.client.table(BLOCKS)
            .select("blocked_id, created_at")
            .eq("blocker_id", blocker_id)
            .order("created_at", desc=True)
            .execute()
        ).data or []
        if not rows:
            return []

        ids = [r["blocked_id"] for r in rows]
        profiles = (self.client.table("user_profiles").select("id, username").in_("id", ids).execute()).data or []
        usernames = {p["id"]: p.get("username") for p in profiles}
        return [
            {"user_id": r["blocked_id"], "username": usernames.get(r["blocked_id"]), "created_at": r["created_at"]}
            for r in rows
        ]

    def blocked_user_ids(self, blocker_id: str) -> list[str]:
        """Ids `blocker_id` has blocked. Empty on error: hiding is best effort,
        and a failed lookup must not take the live view down with it."""
        try:
            rows = self.client.table(BLOCKS).select("blocked_id").eq("blocker_id", blocker_id).execute().data or []
            return [r["blocked_id"] for r in rows]
        except Exception:
            logger.exception("blocked_user_ids_failed", blocker_id=blocker_id)
            return []

    # ------------------------------------------------------------------
    # Bans
    # ------------------------------------------------------------------

    def is_chat_banned(self, user_id: str) -> bool:
        """Whether an admin has removed this user from chat.

        False on error, logged: a failed lookup (or the column not yet
        migrated) must not take chat down for everyone. The filter, reports
        and blocks still apply.
        """
        try:
            rows = self.client.table("user_profiles").select("chat_banned_at").eq("id", user_id).limit(1).execute().data
        except Exception:
            logger.exception("is_chat_banned_failed", user_id=user_id)
            return False
        return bool(rows and rows[0].get("chat_banned_at"))

    def ban_from_chat(self, user_id: str) -> None:
        """Set chat_banned_at, keeping the first ban's timestamp."""
        (
            self.client.table("user_profiles")
            .update({"chat_banned_at": datetime.now(UTC).isoformat()})
            .eq("id", user_id)
            .is_("chat_banned_at", "null")
            .execute()
        )
        logger.info("user_chat_banned", user_id=user_id)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def create_report(
        self,
        *,
        event: dict,
        reporter_id: str,
        reason: str,
        details: str | None,
    ) -> dict | None:
        """Record a report of a chat message.

        Returns the new row, or None when this reporter has already reported
        this message (the unique key makes a repeat a no-op).
        """
        row = {
            "event_id": event["id"],
            "match_id": event["match_id"],
            "reporter_id": reporter_id,
            "reported_user_id": event.get("created_by"),
            "reported_username": event.get("created_by_username"),
            "message_text": event.get("message") or "",
            "reason": reason,
            "details": details,
        }
        try:
            response = self.client.table(REPORTS).insert(row).execute()
        except Exception as exc:
            if _is_pg_error(exc, _UNIQUE_VIOLATION):
                return None
            raise
        return response.data[0] if response.data else None

    def list_reports(self, status: str | None = None, limit: int = 100) -> list[dict]:
        """Reports, newest first, optionally filtered by status."""
        query = self.client.table(REPORTS).select("*").order("created_at", desc=True).limit(limit)
        if status:
            query = query.eq("status", status)
        return query.execute().data or []

    def get_report(self, report_id: int) -> dict | None:
        rows = self.client.table(REPORTS).select("*").eq("id", report_id).limit(1).execute().data
        return rows[0] if rows else None

    def resolve_report(self, report_id: int, *, status: str, action: str, resolved_by: str) -> dict | None:
        response = (
            self.client.table(REPORTS)
            .update(
                {
                    "status": status,
                    "action": action,
                    "resolved_by": resolved_by,
                    "resolved_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", report_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def count_pending_reports(self) -> int:
        response = self.client.table(REPORTS).select("id", count="exact").eq("status", "pending").execute()
        return response.count or 0

    def count_reports_since(self, since_iso: str) -> int:
        """Reports created since `since_iso` — the alert cap's window."""
        response = self.client.table(REPORTS).select("id", count="exact").gte("created_at", since_iso).execute()
        return response.count or 0
