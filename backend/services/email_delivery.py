"""
Invitation email delivery status from Resend webhooks (SB-1814).

The invite send stores Resend's email id on the invitation; the webhook
handler hands every delivery event here. Pure helpers decide what an event
means and whether it may overwrite what is already recorded;
record_delivery_event does the lookup and a compare-and-set write.

Unknown email ids are routine, not errors: support replies (email_outbound),
password resets and invites sent before SB-1814 all produce events too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from services.email_service import _mask

logger = structlog.get_logger(__name__)

# Resend event type → invitations.email_status. email.opened, email.clicked
# and email.scheduled are deliberately absent: they say nothing about delivery.
EVENT_STATUS: dict[str, str] = {
    "email.sent": "sent",
    "email.delivery_delayed": "delayed",
    "email.delivered": "delivered",
    "email.bounced": "bounced",
    "email.complained": "complained",
    "email.failed": "failed",
    "email.suppressed": "suppressed",
}

# Events can arrive late or out of order, and Resend retries. A status only
# replaces a lower-ranked one: delivered never overwrites bounced, while a
# complaint after delivery still wins. The final outcomes share a rank, so the
# first one recorded stays.
_RANK: dict[str, int] = {
    "sent": 0,
    "delayed": 1,
    "delivered": 2,
    "bounced": 3,
    "complained": 3,
    "failed": 3,
    "suppressed": 3,
}

_DETAIL_MAX = 60


def status_for_event(event_type: str | None) -> str | None:
    """The email_status an event type maps to, or None for one we ignore."""
    return EVENT_STATUS.get(event_type or "")


def should_apply(current: str | None, new: str) -> bool:
    """Whether `new` may replace the recorded `current` status."""
    if current is None:
        return True
    return _RANK[new] > _RANK.get(current, -1)


def bounce_detail(data: dict[str, Any]) -> str | None:
    """Short generic bounce reason, e.g. "Permanent: Suppressed".

    Built only from the bounce type and subType. bounce.message is the raw
    SMTP diagnostic, which can carry addresses and server internals, and is
    never stored.
    """
    bounce = data.get("bounce")
    if not isinstance(bounce, dict):
        return None
    parts = [str(p).strip() for p in (bounce.get("type"), bounce.get("subType")) if p]
    detail = ": ".join(p for p in parts if p)
    return detail[:_DETAIL_MAX] or None


def _first_recipient(data: dict[str, Any]) -> str | None:
    to = data.get("to")
    if isinstance(to, list) and to:
        return str(to[0])
    return to if isinstance(to, str) else None


def record_delivery_event(client: Any, event: dict[str, Any]) -> dict[str, Any]:
    """Apply one Resend delivery event to the invitation it belongs to.

    Returns the webhook response body. Never raises for an event we cannot
    use (unknown type, no email id, no matching invitation): Resend disables
    an endpoint that keeps failing, so those are all 200 "ignored". Database
    errors do propagate, so Resend retries a transient failure.
    """
    event_type = event.get("type")
    new_status = status_for_event(event_type)
    data = event.get("data") or {}
    email_id = data.get("email_id")
    if not new_status or not email_id:
        logger.info("email_delivery_ignored_event", event_type=event_type)
        return {"status": "ignored", "event_type": event_type}

    recipient = _mask(_first_recipient(data))
    response = client.table("invitations").select("id, email_status").eq("resend_email_id", email_id).limit(1).execute()
    if not response.data:
        logger.info(
            "email_delivery_no_invitation",
            event_type=event_type,
            email_id=email_id,
            recipient=recipient,
        )
        return {"status": "ignored", "event_type": event_type}

    invitation = response.data[0]
    current = invitation.get("email_status")
    if not should_apply(current, new_status):
        logger.info(
            "email_delivery_unchanged",
            invitation_id=invitation["id"],
            current=current,
            event_status=new_status,
            recipient=recipient,
        )
        return {"status": "unchanged", "email_status": current}

    update = {
        "email_status": new_status,
        "email_status_at": event.get("created_at") or data.get("created_at") or datetime.now(UTC).isoformat(),
        "email_status_detail": bounce_detail(data) if new_status == "bounced" else None,
    }
    # Compare-and-set: only write over the status we read, and only while the
    # invite still points at this email (a resend replaces the id).
    query = client.table("invitations").update(update).eq("id", invitation["id"]).eq("resend_email_id", email_id)
    query = query.is_("email_status", "null") if current is None else query.eq("email_status", current)
    query.execute()

    logger.info(
        "email_delivery_recorded",
        invitation_id=invitation["id"],
        previous=current,
        email_status=new_status,
        recipient=recipient,
    )
    return {"status": "recorded", "email_status": new_status}
