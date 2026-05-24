"""
Outbound-reply primitives for the Support Inbox (SB-35 Phase 2).

Pure helpers + a thin orchestrator the admin-API route can call to send
a reply on an existing thread.

- generate_message_id()              fresh RFC-5322 Message-ID, ours-namespaced
- prefix_subject_with_case_number()  idempotent [MT-{n}] prefix
- build_references()                 References chain, deduped
- send_admin_reply()                 orchestrates: send via Resend + persist + transition
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import resend
import structlog

from services.email_service import SUPPORT_EMAIL, ensure_resend_api_key

if TYPE_CHECKING:
    from dao.email_messages_dao import EmailMessagesDAO
    from dao.email_threads_dao import EmailThreadsDAO

logger = structlog.get_logger()


_MESSAGE_ID_DOMAIN = "missingtable.com"
_REPLY_PREFIX_RE = re.compile(r"^\s*(?:re|fwd?|fw)\s*:\s*", re.IGNORECASE)


def generate_message_id() -> str:
    """Return a stable, ours-namespaced Message-ID without angle brackets.

    Storage form is angle-bracket-stripped for parity with inbound (we
    strip them at ingest). Callers wrap in `<>` when setting the actual
    Message-ID header on the outgoing email.
    """
    return f"mt-{uuid.uuid4()}@{_MESSAGE_ID_DOMAIN}"


def prefix_subject_with_case_number(subject: str | None, case_number: int) -> str:
    """Ensure the subject carries `[MT-{case_number}]` and starts with `Re: `.

    Idempotent: calling twice produces the same string. Examples (case_number=1):
        "My Question"                    → "Re: [MT-1] My Question"
        "Re: My Question"                → "Re: [MT-1] My Question"
        "Re: Re: My Question"            → "Re: [MT-1] My Question"
        "[MT-1] My Question"             → "Re: [MT-1] My Question"
        "Re: [MT-1] My Question"         → "Re: [MT-1] My Question"  (unchanged)
        "Re: Re: [MT-1] My Question"     → "Re: Re: [MT-1] My Question"  (unchanged)
    """
    raw = (subject or "").strip()
    token_re = re.compile(rf"\[\s*MT-{case_number}\s*\]", re.IGNORECASE)

    if token_re.search(raw):
        # Already tagged — just make sure it reads like a reply.
        if _REPLY_PREFIX_RE.match(raw):
            return raw
        return f"Re: {raw}"

    # Collapse any leading Re:/Fwd:/Fw: chain before inserting the tag.
    stripped = raw
    while True:
        nxt = _REPLY_PREFIX_RE.sub("", stripped, count=1)
        if nxt == stripped:
            break
        stripped = nxt

    body = stripped or "(no subject)"
    return f"Re: [MT-{case_number}] {body}"


def build_references(existing_references: str | None, in_reply_to_id: str | None) -> str:
    """Append `in_reply_to_id` (angle-bracketed) to the existing References
    chain, deduped, whitespace-separated. Returns an empty string when both
    inputs are empty.
    """
    ids: list[str] = (existing_references or "").split()
    if in_reply_to_id:
        bracketed = (
            in_reply_to_id if in_reply_to_id.startswith("<") else f"<{in_reply_to_id}>"
        )
        if bracketed not in ids:
            ids.append(bracketed)
    return " ".join(ids)


def _strip_angle_brackets(value: str | None) -> str | None:
    """Mirror of the inbound webhook helper. RFC 5322 Message-IDs are wrapped
    in `<>`. Strip them for storage so equality lookups don't care about wrapping.
    """
    if not value:
        return value
    s = value.strip()
    if s.startswith("<") and s.endswith(">"):
        return s[1:-1]
    return s


def send_admin_reply(
    threads_dao: EmailThreadsDAO,
    messages_dao: EmailMessagesDAO,
    *,
    thread: dict[str, Any],
    body_text: str,
    body_html: str | None,
    admin_user_id: str,
) -> dict[str, Any]:
    """Send an outbound admin reply on a thread, then persist + transition.

    Steps:
    1. Look up the latest inbound message to set In-Reply-To + extend References.
    2. Generate a fresh Message-ID; prefix the subject idempotently.
    3. Call `resend.Emails.send` (with `ensure_resend_api_key()` first — lesson
       #2 from Phase 1 applies here too).
    4. Persist the outbound message and transition the thread to `awaiting_user`.

    Returns the inserted message row.

    Raises RuntimeError on send failure — caller maps to 5xx.
    """
    latest_inbound = messages_dao.get_latest_inbound_for_thread(thread["id"])

    in_reply_to_stripped = (
        latest_inbound["message_id"] if latest_inbound else None
    )
    in_reply_to_bracketed = (
        f"<{in_reply_to_stripped}>" if in_reply_to_stripped else None
    )
    references = build_references(
        latest_inbound.get("references") if latest_inbound else None,
        in_reply_to_stripped,
    )

    subject = prefix_subject_with_case_number(
        thread.get("subject"), thread["case_number"]
    )

    message_id = generate_message_id()  # stored stripped
    message_id_bracketed = f"<{message_id}>"

    to_email = thread["participant_email"]

    custom_headers: dict[str, str] = {"Message-ID": message_id_bracketed}
    if in_reply_to_bracketed:
        custom_headers["In-Reply-To"] = in_reply_to_bracketed
    if references:
        custom_headers["References"] = references

    payload: dict[str, Any] = {
        "from": SUPPORT_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": body_text,
        "headers": custom_headers,
    }
    if body_html:
        payload["html"] = body_html

    ensure_resend_api_key()
    try:
        resend.Emails.send(payload)
    except Exception as e:
        logger.exception(
            "admin_reply_send_failed",
            thread_id=thread["id"],
            case_number=thread["case_number"],
        )
        raise RuntimeError(f"failed to send admin reply: {e}") from e

    now_iso = datetime.now(UTC).isoformat()
    row = messages_dao.insert_outbound(
        thread_id=thread["id"],
        message_id=message_id,
        from_email=SUPPORT_EMAIL,
        to_email=to_email,
        subject=subject,
        sent_by_user_id=admin_user_id,
        in_reply_to=in_reply_to_stripped,
        references=references or None,
        body_text=body_text,
        body_html=body_html,
    )
    threads_dao.transition_on_outbound(thread["id"], last_message_at=now_iso)

    logger.info(
        "admin_reply_sent",
        thread_id=thread["id"],
        case_number=thread["case_number"],
        message_id=message_id,
        admin_user_id=admin_user_id,
    )
    return row
