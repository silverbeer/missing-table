"""
EmailMessagesDAO — individual messages in support-inbox threads (SB-35).

Phase 1 surface (webhook ingest): insert_inbound, find_by_message_id,
find_thread_id_by_in_reply_to. Phase 2 (admin API) will add list_by_thread
and insert_outbound for admin replies.
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
