"""
Inbound email webhook (Resend Inbound → support@missingtable.com).

Verifies the provider's Svix signature, fetches the full ReceivedEmail
via the Resend API, runs the threading resolver, sanitizes any HTML,
and persists the message. Idempotent on RFC 5322 Message-ID so
provider retries are safe.

SB-35 Phase 1. The admin API (Phase 2) and admin UI (Phase 3) consume
the rows we land here.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import resend
import structlog
from fastapi import APIRouter, HTTPException, Request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dao.email_messages_dao import EmailMessagesDAO
from dao.email_threads_dao import EmailThreadsDAO
from dao.match_dao import SupabaseConnection as DbConnectionHolder
from services.email_inbound import (
    WebhookVerificationError,
    resolve_thread,
    sanitize_html,
    verify_webhook,
)

logger = structlog.get_logger(__name__)

# Inbound writes bypass RLS via the service-role connection — the webhook
# can't authenticate as a user, and HMAC verification is the trust gate.
_db_conn = DbConnectionHolder()
_threads_dao = EmailThreadsDAO(_db_conn)
_messages_dao = EmailMessagesDAO(_db_conn)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

_INBOUND_EVENT_TYPE = "email.received"


def _strip_angle_brackets(value: str | None) -> str | None:
    """RFC 5322 Message-IDs are wrapped in `<>`. Strip them for storage so
    our equality lookups don't have to care about the wrapping."""
    if not value:
        return value
    stripped = value.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return stripped[1:-1]
    return stripped


def _header_lookup(headers: dict[str, str] | None, *names: str) -> str | None:
    """Case-insensitive header lookup. Returns the first match."""
    if not headers:
        return None
    lower = {k.lower(): v for k, v in headers.items()}
    for name in names:
        value = lower.get(name.lower())
        if value:
            return value
    return None


def _extract_display_name(from_header: str) -> tuple[str, str | None]:
    """Parse a `"Jane Doe" <jane@example.com>` style From header into
    (address, display_name). Falls back to (raw, None) on anything weird."""
    raw = from_header.strip()
    if "<" in raw and raw.endswith(">"):
        name_part, _, addr_part = raw.rpartition("<")
        name = name_part.strip().strip('"').strip() or None
        return addr_part[:-1].strip(), name
    return raw, None


@router.post("/email/inbound")
async def email_inbound(request: Request) -> dict[str, Any]:
    """Receive an `email.received` event from Resend Inbound.

    Returns 200 on:
    - Successful ingest
    - Unknown event type (we ignore quietly so Resend doesn't retry)
    - Already-seen Message-ID (idempotent retry)

    Returns 401 on signature mismatch.
    Returns 500 on internal failure — Resend will retry.
    """
    raw_body = await request.body()
    payload_str = raw_body.decode("utf-8")

    # Forward only the headers the verifier needs — keeps logs cleaner.
    svix_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower().startswith("svix-")
    }

    try:
        verify_webhook(payload=payload_str, headers=svix_headers)
    except WebhookVerificationError as e:
        logger.warning("email_webhook_unauthorized", error=str(e))
        raise HTTPException(status_code=401, detail="invalid webhook signature") from e

    try:
        event = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logger.warning("email_webhook_bad_json", error=str(e))
        raise HTTPException(status_code=400, detail="invalid JSON payload") from e

    event_type = event.get("type")
    if event_type != _INBOUND_EVENT_TYPE:
        logger.info("email_webhook_ignored_event", event_type=event_type)
        return {"status": "ignored", "event_type": event_type}

    data = event.get("data") or {}
    email_id = data.get("email_id") or data.get("id")
    if not email_id:
        # `event` is reserved by structlog — use a different key.
        logger.warning("email_webhook_missing_email_id", payload=event)
        raise HTTPException(status_code=400, detail="event.data.email_id missing")

    received = _fetch_received_email(email_id)

    raw_message_id = received.get("message_id")
    message_id = _strip_angle_brackets(raw_message_id)
    if not message_id:
        logger.warning("email_webhook_missing_message_id", email_id=email_id)
        raise HTTPException(status_code=400, detail="received email has no message_id")

    # Idempotency: if we've seen this message_id already, Resend retried.
    existing = _messages_dao.find_by_message_id(message_id)
    if existing:
        logger.info(
            "email_webhook_duplicate",
            message_id=message_id,
            thread_id=existing["thread_id"],
        )
        return {
            "status": "duplicate",
            "message_id": message_id,
            "thread_id": existing["thread_id"],
        }

    # ── Extract envelope fields ─────────────────────────────────────────────
    headers = received.get("headers") or received.get("http_headers") or {}
    in_reply_to = _strip_angle_brackets(_header_lookup(headers, "In-Reply-To"))
    references = _header_lookup(headers, "References")

    from_raw = received.get("from") or ""
    from_email, from_name = _extract_display_name(from_raw)
    to_list = received.get("to") or []
    to_email = to_list[0] if to_list else ""

    subject = received.get("subject") or "(no subject)"
    body_text = received.get("text")
    body_html_raw = received.get("html")
    had_attachments = bool(received.get("attachments"))

    # ── Resolve / create thread ─────────────────────────────────────────────
    last_message_at_iso = received.get("created_at")
    thread, created = resolve_thread(
        _threads_dao,
        _messages_dao,
        subject=subject,
        from_email=from_email,
        from_name=from_name,
        in_reply_to=in_reply_to,
        last_message_at_iso=last_message_at_iso,
    )

    # ── Insert inbound message ──────────────────────────────────────────────
    sanitized_html = sanitize_html(body_html_raw)
    # raw_payload omits attachments — we don't want the base64 bodies in pg.
    raw_for_storage = {k: v for k, v in received.items() if k != "attachments"}

    _messages_dao.insert_inbound(
        thread_id=thread["id"],
        message_id=message_id,
        from_email=from_email,
        from_name=from_name,
        to_email=to_email,
        subject=subject,
        in_reply_to=in_reply_to,
        references=references,
        body_text=body_text,
        body_html=sanitized_html,
        had_attachments=had_attachments,
        raw_payload=raw_for_storage,
    )

    # ── Status transition for existing threads ──────────────────────────────
    # New threads start at status='new' with unread_count=1 (create_for_inbound
    # already set both), so only transition existing threads.
    if not created:
        _threads_dao.transition_on_inbound(
            thread["id"], last_message_at=last_message_at_iso
        )

    logger.info(
        "email_webhook_ingested",
        thread_id=thread["id"],
        case_number=thread["case_number"],
        message_id=message_id,
        created_new_thread=created,
        had_attachments=had_attachments,
    )
    return {
        "status": "accepted",
        "thread_id": thread["id"],
        "case_number": thread["case_number"],
        "created_new_thread": created,
    }


def _fetch_received_email(email_id: str) -> dict[str, Any]:
    """Fetch the full ReceivedEmail from the Resend API.

    Returns the underlying dict (ReceivedEmail is a TypedDict). Raised
    exceptions become 502 from the caller's perspective — Resend will
    retry, which is the right behavior for transient upstream failures.
    """
    try:
        return resend.Emails.Receiving.get(email_id)
    except Exception as e:
        logger.exception("email_webhook_fetch_failed", email_id=email_id)
        raise HTTPException(status_code=502, detail=f"failed to fetch email {email_id}") from e
