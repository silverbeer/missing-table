"""
Inbound-email primitives for the Support Inbox (SB-35 Phase 1).

Pure-ish helpers consumed by the inbound webhook handler:
- verify_webhook  — wraps resend.Webhooks.verify with env-driven secret + typed errors
- sanitize_html   — bleach allowlist; never store raw provider HTML
- parse_case_number_from_subject — `[MT-{n}]` extractor for threading fallback
- normalize_subject — strips Re:/Fwd: + case-number tokens for fuzzy match
- resolve_thread  — 4-tier threading resolver (creates a new thread if no match)
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import bleach
import resend
import structlog

if TYPE_CHECKING:
    from dao.email_messages_dao import EmailMessagesDAO
    from dao.email_threads_dao import EmailThreadsDAO

logger = structlog.get_logger()


class WebhookVerificationError(Exception):
    """Raised when the inbound webhook signature can't be verified."""


# ── HMAC verification ────────────────────────────────────────────────────────


def verify_webhook(*, payload: str, headers: dict[str, str]) -> None:
    """Verify a Resend inbound webhook using its Svix-based signature.

    Loads the secret from EMAIL_INBOUND_WEBHOOK_SECRET. The payload must be
    the raw request body string (not parsed JSON) — Svix is sensitive to
    even whitespace differences.

    Raises WebhookVerificationError on any failure (missing secret,
    missing headers, bad signature). The webhook handler should catch
    this and return 401.
    """
    secret = os.getenv("EMAIL_INBOUND_WEBHOOK_SECRET")
    if not secret:
        raise WebhookVerificationError(
            "EMAIL_INBOUND_WEBHOOK_SECRET is not configured"
        )

    required = {"svix-id", "svix-timestamp", "svix-signature"}
    lowered = {k.lower(): v for k, v in headers.items()}
    missing = required - lowered.keys()
    if missing:
        raise WebhookVerificationError(
            f"Missing required webhook header(s): {sorted(missing)}"
        )

    # Resend's WebhookHeaders TypedDict uses the short keys `id`/`timestamp`/
    # `signature` (the `svix-` prefix is stripped). The field-level docstring
    # says "The svix-id header value" but the field is named just `id`, so
    # we must remap before calling verify — passing the prefixed HTTP-header
    # names through results in "svix-id header is required" failures.
    try:
        resend.Webhooks.verify(
            resend.VerifyWebhookOptions(
                payload=payload,
                headers={
                    "id": lowered["svix-id"],
                    "timestamp": lowered["svix-timestamp"],
                    "signature": lowered["svix-signature"],
                },
                webhook_secret=secret,
            )
        )
    except Exception as e:
        raise WebhookVerificationError(f"Signature verification failed: {e}") from e


# ── HTML sanitization ────────────────────────────────────────────────────────

# Conservative allowlist for displayed email content. We don't trust the
# inbound payload, so we strip everything not in this set. Bleach also
# rejects javascript: hrefs by default given the protocol allowlist below.
_ALLOWED_TAGS = frozenset({
    "a", "b", "blockquote", "br", "code", "div", "em", "hr",
    "i", "li", "ol", "p", "pre", "span", "strong", "u", "ul",
})
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "span": ["class"],
    "div": ["class"],
}
_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


def sanitize_html(raw: str | None) -> str | None:
    """Sanitize untrusted inbound HTML with a conservative allowlist.

    Returns None for None input (so we can pass it through). Strips
    disallowed tags rather than escaping them — we never want raw HTML
    rendered into the admin UI.
    """
    if raw is None:
        return None
    return bleach.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )


# ── Case-number / subject parsing ────────────────────────────────────────────

# Matches `[MT-1234]` (any leading/trailing space) and captures the digits.
# Case-insensitive on "MT". Doesn't match `MT-1234` without brackets — we
# always render the case number bracketed in outbound subjects, and we
# don't want to false-match other patterns in subjects.
_CASE_RE = re.compile(r"\[\s*MT-(\d+)\s*\]", re.IGNORECASE)

# Strips Re:/Fwd:/Fw: prefixes, possibly chained ("Re: Re: Re:"). Match
# at the start, repeat. Case-insensitive, optional surrounding whitespace.
_REPLY_PREFIX_RE = re.compile(r"^\s*(?:re|fwd?|fw)\s*:\s*", re.IGNORECASE)


def parse_case_number_from_subject(subject: str | None) -> int | None:
    """Return the integer case number embedded as `[MT-{n}]`, or None."""
    if not subject:
        return None
    m = _CASE_RE.search(subject)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def normalize_subject(subject: str | None) -> str:
    """Subject form used for fuzzy thread matching.

    - strips chained Re:/Fwd: prefixes
    - removes any [MT-{n}] token
    - collapses internal whitespace
    - lowercases
    """
    if not subject:
        return ""
    s = _CASE_RE.sub("", subject)
    while True:
        new = _REPLY_PREFIX_RE.sub("", s)
        if new == s:
            break
        s = new
    return " ".join(s.split()).lower()


# ── Threading resolver ───────────────────────────────────────────────────────

# Window for the fuzzy fallback. Anything older and we'd rather start a
# new thread than risk merging unrelated conversations.
_FALLBACK_WINDOW = timedelta(days=30)


def resolve_thread(
    threads_dao: EmailThreadsDAO,
    messages_dao: EmailMessagesDAO,
    *,
    subject: str,
    from_email: str,
    from_name: str | None,
    in_reply_to: str | None,
    last_message_at_iso: str | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    """Resolve the email_threads row this inbound message belongs to.

    Returns (thread_row, created), where `created` is True if a new thread
    was inserted.

    Fallback chain (in order):
    1. `In-Reply-To` matches a known message_id → reuse its thread
    2. `[MT-{n}]` in subject → reuse the matching thread by case_number
    3. Same participant + same normalized subject within the last 30 days
       → reuse the most recent matching thread
    4. Nothing matched → create a new thread (assigns a fresh case number)
    """
    # 1) In-Reply-To
    if in_reply_to:
        thread_id = messages_dao.find_thread_id_by_in_reply_to(in_reply_to)
        if thread_id:
            existing = threads_dao.get_thread_by_id(thread_id)
            if existing:
                logger.info(
                    "email_thread_resolved",
                    via="in_reply_to",
                    thread_id=existing["id"],
                    case_number=existing["case_number"],
                )
                return existing, False

    # 2) [MT-{n}] in subject
    case_number = parse_case_number_from_subject(subject)
    if case_number is not None:
        existing = threads_dao.get_by_case_number(case_number)
        if existing:
            logger.info(
                "email_thread_resolved",
                via="case_number",
                thread_id=existing["id"],
                case_number=existing["case_number"],
            )
            return existing, False

    # 3) Recent participant + same normalized subject
    normalized = normalize_subject(subject)
    if normalized:
        since = (now or datetime.now(UTC)) - _FALLBACK_WINDOW
        candidates = threads_dao.find_recent_by_participant(
            from_email,
            since_iso=since.isoformat(),
        )
        for candidate in candidates:
            if normalize_subject(candidate.get("subject")) == normalized:
                logger.info(
                    "email_thread_resolved",
                    via="participant_subject",
                    thread_id=candidate["id"],
                    case_number=candidate["case_number"],
                )
                return candidate, False

    # 4) New thread
    created = threads_dao.create_for_inbound(
        subject=subject or "(no subject)",
        participant_email=from_email,
        participant_name=from_name,
        last_message_at=last_message_at_iso,
    )
    logger.info(
        "email_thread_resolved",
        via="new",
        thread_id=created["id"],
        case_number=created["case_number"],
    )
    return created, True
