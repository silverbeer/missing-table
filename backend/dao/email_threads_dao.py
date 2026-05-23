"""
EmailThreadsDAO — support-inbox conversations (SB-35).

Phase 1 surface (webhook ingest): create_for_inbound, transition_on_inbound,
get_by_id, get_by_case_number. Phase 2 (admin API) will add listing,
status overrides, and outbound-reply transitions.
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO, invalidates_cache

logger = structlog.get_logger()

EMAIL_THREADS_CACHE_PATTERN = "mt:dao:email_threads:*"


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
