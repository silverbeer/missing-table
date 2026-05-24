"""
EmailThreadsDAO — support-inbox conversations (SB-35).

Phase 1 surface (webhook ingest): create_for_inbound, transition_on_inbound,
get_by_id, get_by_case_number.

Phase 2 surface (admin API): list_by_status, get_thread_with_messages,
transition_on_outbound, set_status, mark_all_read, unread_count_for_attention.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

import structlog

from dao.base_dao import BaseDAO, invalidates_cache

logger = structlog.get_logger()

EMAIL_THREADS_CACHE_PATTERN = "mt:dao:email_threads:*"
EMAIL_MESSAGES_CACHE_PATTERN = "mt:dao:email_messages:*"

_VALID_STATUSES = frozenset({"new", "awaiting_admin", "awaiting_user", "resolved", "spam"})
_MANUAL_STATUSES = frozenset({"resolved", "spam", "awaiting_admin"})


def encode_cursor(last_message_at: str, thread_id: str) -> str:
    """Opaque cursor for keyset pagination on (last_message_at desc, id desc).

    Base64-encoded so callers don't depend on the internal shape.
    """
    raw = f"{last_message_at}|{thread_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Inverse of encode_cursor. Returns (last_message_at, thread_id)."""
    padded = cursor + "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(padded).decode()
    ts, _, tid = raw.partition("|")
    if not ts or not tid:
        raise ValueError("invalid cursor")
    return ts, tid


class EmailThreadsDAO(BaseDAO):
    """Data access for the email_threads table."""

    # ── reads ────────────────────────────────────────────────────────────────

    def get_thread_by_id(self, thread_id: str) -> dict[str, Any] | None:
        """Fetch a thread by UUID. Returns None if not found.

        Named `get_thread_by_id` (rather than `get_by_id`) so the typed UUID
        argument doesn't collide with BaseDAO.get_by_id(table, record_id).
        """
        response = (
            self.client.table("email_threads")
            .select("*")
            .eq("id", thread_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def find_recent_by_participant(
        self,
        participant_email: str,
        *,
        since_iso: str,
    ) -> list[dict[str, Any]]:
        """Recent threads from a participant, newest first.

        Used by the threading resolver's third-tier fallback: when neither
        In-Reply-To nor a case-number-in-subject matches, look for a recent
        thread from the same sender and merge by normalized subject upstream.

        Args:
            participant_email: external party's address (case-insensitive match)
            since_iso: ISO timestamp lower bound (e.g. now - 30 days)
        """
        response = (
            self.client.table("email_threads")
            .select("*")
            .ilike("participant_email", participant_email)
            .gte("last_message_at", since_iso)
            .order("last_message_at", desc=True)
            .limit(20)
            .execute()
        )
        return response.data or []

    def get_by_case_number(self, case_number: int) -> dict[str, Any] | None:
        """Fetch a thread by its MT-{n} case number. Returns None if not found.

        Used by the threading resolver (fallback when In-Reply-To is missing
        but the inbound subject contains `[MT-{n}]`) and by the admin UI for
        deep-linking by case number.
        """
        response = (
            self.client.table("email_threads")
            .select("*")
            .eq("case_number", case_number)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    # ── writes ───────────────────────────────────────────────────────────────

    @invalidates_cache(EMAIL_THREADS_CACHE_PATTERN)
    def create_for_inbound(
        self,
        *,
        subject: str,
        participant_email: str,
        participant_name: str | None = None,
        last_message_at: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new thread for an inbound email that didn't match any
        existing thread. case_number is assigned automatically from the
        sequence; status starts as 'new'; unread_count is set to 1 since
        this insert always pairs with an inbound message.

        Args:
            subject: subject line of the first inbound message
            participant_email: the external party (sender of the inbound)
            participant_name: optional display name from From header
            last_message_at: optional ISO timestamp; defaults to now() in db

        Returns:
            The inserted row (including assigned id and case_number).
        """
        payload: dict[str, Any] = {
            "subject": subject,
            "participant_email": participant_email,
            "participant_name": participant_name,
            "status": "new",
            "unread_count": 1,
        }
        if last_message_at:
            payload["last_message_at"] = last_message_at

        response = self.client.table("email_threads").insert(payload).execute()
        if not response.data:
            raise RuntimeError("email_threads insert returned no data")
        row = response.data[0]
        logger.info(
            "email_thread_created",
            thread_id=row["id"],
            case_number=row["case_number"],
            participant_email=participant_email,
        )
        return row

    @invalidates_cache(EMAIL_THREADS_CACHE_PATTERN)
    def transition_on_inbound(
        self,
        thread_id: str,
        *,
        last_message_at: str | None = None,
    ) -> dict[str, Any] | None:
        """An inbound message just landed on an existing thread.

        Side effects:
        - status: 'new' / 'awaiting_admin' / 'resolved' → 'awaiting_admin'
          (reopens 'resolved' threads on user reply).
        - status: 'spam' → unchanged (silently absorb).
        - unread_count += 1
        - last_message_at = max(existing, last_message_at)
        """
        current = self.get_thread_by_id(thread_id)
        if not current:
            return None

        next_status = current["status"]
        if next_status != "spam":
            next_status = "awaiting_admin"

        updates: dict[str, Any] = {
            "status": next_status,
            "unread_count": (current.get("unread_count") or 0) + 1,
        }
        if last_message_at:
            updates["last_message_at"] = last_message_at

        response = (
            self.client.table("email_threads")
            .update(updates)
            .eq("id", thread_id)
            .execute()
        )
        return response.data[0] if response.data else None

    # ── Phase 2: admin API surface ───────────────────────────────────────────

    def list_by_status(
        self,
        statuses: list[str],
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Paginated list of threads filtered by status, newest-first.

        Keyset cursor on `(last_message_at desc, id desc)` — stable across
        inserts and avoids OFFSET's slow-scan behavior on large inboxes.

        Args:
            statuses: list of status values to include (e.g. ['new', 'awaiting_admin'])
            limit: page size (caller should clamp to a sane max)
            cursor: opaque cursor from a previous call (or None for first page)

        Returns:
            {"items": [thread_dict, ...], "next_cursor": str | None}

            Threads come back with an embedded `message_count` so the admin UI's
            list view doesn't have to N+1.
        """
        query = (
            self.client.table("email_threads")
            .select("*, email_messages(count)")
            .in_("status", statuses)
        )

        if cursor:
            try:
                ts, tid = decode_cursor(cursor)
            except (ValueError, Exception) as e:
                raise ValueError(f"invalid cursor: {e}") from e
            # PostgREST keyset: (last_message_at < ts) OR (last_message_at = ts AND id < tid)
            query = query.or_(
                f"last_message_at.lt.{ts},"
                f"and(last_message_at.eq.{ts},id.lt.{tid})"
            )

        response = (
            query.order("last_message_at", desc=True)
            .order("id", desc=True)
            .limit(limit + 1)
            .execute()
        )
        rows = response.data or []

        # Flatten embedded message_count and trim peek row used for cursor calc.
        for row in rows:
            embedded = row.pop("email_messages", None) or []
            row["message_count"] = embedded[0]["count"] if embedded else 0

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = encode_cursor(last["last_message_at"], last["id"])

        return {"items": rows, "next_cursor": next_cursor}

    def get_thread_with_messages(self, thread_id: str) -> dict[str, Any] | None:
        """Fetch a thread plus all its messages in one round trip.

        Messages are sorted chronologically (oldest first) — the order the
        admin UI renders.
        """
        response = (
            self.client.table("email_threads")
            .select("*, email_messages(*)")
            .eq("id", thread_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        messages = row.pop("email_messages", None) or []
        messages.sort(key=lambda m: m.get("created_at") or "")
        row["messages"] = messages
        return row

    @invalidates_cache(EMAIL_THREADS_CACHE_PATTERN)
    def transition_on_outbound(
        self,
        thread_id: str,
        *,
        last_message_at: str | None = None,
    ) -> dict[str, Any] | None:
        """An outbound admin reply was just sent on this thread.

        Side effects:
        - status → 'awaiting_user' (unconditional — admin has acted)
        - last_message_at = max(existing, last_message_at)

        Symmetric to transition_on_inbound. Does NOT bump unread_count
        (outbound messages aren't "unread" from the admin's perspective).
        """
        updates: dict[str, Any] = {"status": "awaiting_user"}
        if last_message_at:
            updates["last_message_at"] = last_message_at

        response = (
            self.client.table("email_threads")
            .update(updates)
            .eq("id", thread_id)
            .execute()
        )
        return response.data[0] if response.data else None

    @invalidates_cache(EMAIL_THREADS_CACHE_PATTERN)
    def set_status(self, thread_id: str, status: str) -> dict[str, Any] | None:
        """Manual status override from an admin (resolved, spam, awaiting_admin).

        Only the manual-override statuses are accepted here; auto-transitions
        (new, awaiting_user) are owned by the inbound/outbound message paths.
        """
        if status not in _MANUAL_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_MANUAL_STATUSES)}, got {status!r}"
            )
        response = (
            self.client.table("email_threads")
            .update({"status": status})
            .eq("id", thread_id)
            .execute()
        )
        return response.data[0] if response.data else None

    @invalidates_cache(EMAIL_THREADS_CACHE_PATTERN, EMAIL_MESSAGES_CACHE_PATTERN)
    def mark_all_read(self, thread_id: str) -> int:
        """Zero out the thread's unread_count and stamp read_at on every
        previously-unread message. Returns the number of message rows updated.
        """
        now_iso = datetime.now(UTC).isoformat()

        # Stamp unread messages first so we know how many actually changed.
        msg_response = (
            self.client.table("email_messages")
            .update({"read_at": now_iso})
            .eq("thread_id", thread_id)
            .is_("read_at", None)
            .execute()
        )
        updated_count = len(msg_response.data or [])

        self.client.table("email_threads").update({"unread_count": 0}).eq(
            "id", thread_id
        ).execute()

        return updated_count

    def unread_count_for_attention(self) -> int:
        """Sum of unread_count across threads that need admin attention.

        Powers the Phase 3 nav badge. Cacheable upstream for ~30s.
        """
        response = (
            self.client.table("email_threads")
            .select("unread_count")
            .in_("status", ["new", "awaiting_admin"])
            .execute()
        )
        return sum((row.get("unread_count") or 0) for row in (response.data or []))
