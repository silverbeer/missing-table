"""
EmailMessagesDAO — individual messages in support-inbox threads (SB-35).

Phase 1 surface (webhook ingest): insert_inbound, find_by_message_id,
find_thread_id_by_in_reply_to.

Phase 2 surface (admin API): list_by_thread, insert_outbound,
get_latest_inbound_for_thread.
"""

from __future__ import annotations

from typing import Any

import structlog

from dao.base_dao import BaseDAO, invalidates_cache

logger = structlog.get_logger()

EMAIL_MESSAGES_CACHE_PATTERN = "mt:dao:email_messages:*"


class EmailMessagesDAO(BaseDAO):
    """Data access for the email_messages table."""

    # ── reads ────────────────────────────────────────────────────────────────

    def find_by_message_id(self, message_id: str) -> dict[str, Any] | None:
        """Look up a message by its RFC 5322 Message-ID (angle brackets stripped).

        Used for webhook idempotency: if the same provider event arrives twice
        (e.g. Resend retry), the second insert hits the unique constraint —
        but we check first so we can return 200 cleanly without an exception.
        """
        response = (
            self.client.table("email_messages")
            .select("*")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def find_thread_id_by_in_reply_to(self, in_reply_to: str) -> str | None:
        """Resolve the thread an inbound reply belongs to via the In-Reply-To
        header. Returns the thread_id of the referenced message, or None if
        we don't recognize the referenced Message-ID.

        This is the first tier of the threading resolver. Falls back to
        case-number-in-subject and then subject+sender if this misses.
        """
        response = (
            self.client.table("email_messages")
            .select("thread_id")
            .eq("message_id", in_reply_to)
            .limit(1)
            .execute()
        )
        return response.data[0]["thread_id"] if response.data else None

    # ── writes ───────────────────────────────────────────────────────────────

    @invalidates_cache(EMAIL_MESSAGES_CACHE_PATTERN)
    def insert_inbound(
        self,
        *,
        thread_id: str,
        message_id: str,
        from_email: str,
        to_email: str,
        subject: str,
        in_reply_to: str | None = None,
        references: str | None = None,
        from_name: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
        had_attachments: bool = False,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert a new inbound message row.

        Caller is responsible for sanitizing body_html (we never insert raw
        webhook HTML — bleach is applied upstream in the inbound service).

        Raises if the unique constraint on message_id fires; the webhook
        handler checks find_by_message_id first to make ingest idempotent.
        """
        payload: dict[str, Any] = {
            "thread_id": thread_id,
            "direction": "inbound",
            "message_id": message_id,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "in_reply_to": in_reply_to,
            "references": references,
            "from_name": from_name,
            "body_text": body_text,
            "body_html": body_html,
            "had_attachments": had_attachments,
            "raw_payload": raw_payload,
        }
        response = self.client.table("email_messages").insert(payload).execute()
        if not response.data:
            raise RuntimeError("email_messages insert returned no data")
        row = response.data[0]
        logger.info(
            "email_message_inserted",
            message_id=message_id,
            thread_id=thread_id,
            direction="inbound",
            had_attachments=had_attachments,
        )
        return row

    # ── Phase 2: admin API surface ───────────────────────────────────────────

    def list_by_thread(self, thread_id: str) -> list[dict[str, Any]]:
        """All messages in a thread, oldest first."""
        response = (
            self.client.table("email_messages")
            .select("*")
            .eq("thread_id", thread_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []

    def get_latest_inbound_for_thread(
        self, thread_id: str
    ) -> dict[str, Any] | None:
        """The most recent inbound message on a thread. Used by the admin-reply
        path to set In-Reply-To on the outgoing message.
        """
        response = (
            self.client.table("email_messages")
            .select("*")
            .eq("thread_id", thread_id)
            .eq("direction", "inbound")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    @invalidates_cache(EMAIL_MESSAGES_CACHE_PATTERN)
    def insert_outbound(
        self,
        *,
        thread_id: str,
        message_id: str,
        from_email: str,
        to_email: str,
        subject: str,
        sent_by_user_id: str,
        in_reply_to: str | None = None,
        references: str | None = None,
        body_text: str | None = None,
        body_html: str | None = None,
    ) -> dict[str, Any]:
        """Insert an outbound admin-reply message row.

        Symmetric to insert_inbound, but the caller is the admin sending
        the reply — sent_by_user_id is required and direction is 'outbound'.
        had_attachments and raw_payload don't apply (we don't attach files
        or have a provider payload to preserve on outbound).

        message_id should be the angle-brackets-stripped form, for parity
        with inbound storage (so In-Reply-To lookups work in both directions).
        """
        payload: dict[str, Any] = {
            "thread_id": thread_id,
            "direction": "outbound",
            "message_id": message_id,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "in_reply_to": in_reply_to,
            "references": references,
            "body_text": body_text,
            "body_html": body_html,
            "had_attachments": False,
            "sent_by_user_id": sent_by_user_id,
        }
        response = self.client.table("email_messages").insert(payload).execute()
        if not response.data:
            raise RuntimeError("email_messages insert returned no data")
        row = response.data[0]
        logger.info(
            "email_message_inserted",
            message_id=message_id,
            thread_id=thread_id,
            direction="outbound",
            sent_by_user_id=sent_by_user_id,
        )
        return row
