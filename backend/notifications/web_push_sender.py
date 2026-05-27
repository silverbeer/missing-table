"""Web Push sender.

Wraps pywebpush. Reads VAPID config from env. Auto-cleans subscriptions
the push service rejects as gone (404 / 410) so push_send_log doesn't
fill with permanent failures.

Never raises to the caller — returns a SendResult that the dispatcher
can log without breaking the user-facing flow.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# Statuses written to push_send_log.status
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"  # subscription gone — cleaned up


@dataclass(frozen=True)
class SendResult:
    """Outcome of one push send attempt."""

    status: str  # one of STATUS_*
    http_status: int | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == STATUS_SENT

    @property
    def expired(self) -> bool:
        return self.status == STATUS_EXPIRED


def is_configured() -> bool:
    """True if VAPID env vars are all set. Backend boots without them
    (push fan-out is a no-op until configured).
    """
    return bool(
        os.getenv("VAPID_PRIVATE_KEY")
        and os.getenv("VAPID_PUBLIC_KEY")
        and os.getenv("VAPID_SUBJECT")
    )


def get_public_key() -> str | None:
    """Public VAPID key (returned to the frontend at runtime). Non-secret."""
    return os.getenv("VAPID_PUBLIC_KEY") or None


def send_push(
    subscription: dict[str, Any],
    payload: dict[str, Any],
    *,
    ttl: int = 60,
) -> SendResult:
    """Send a single Web Push message. Never raises.

    subscription dict must include `endpoint`, `p256dh_key`, `auth_key`.
    payload is JSON-serialized and sent as the message body — the service
    worker on the client parses it in the `push` event handler.

    ttl: how long the push service should hold the message if the device
    is offline. 60s is a sensible default for time-sensitive match events
    (a goal that arrives 5 minutes late is just noise).
    """
    if not is_configured():
        # Log once per process at registration time; here just skip silently.
        return SendResult(status=STATUS_FAILED, error="VAPID not configured")

    endpoint = subscription.get("endpoint")
    p256dh = subscription.get("p256dh_key")
    auth = subscription.get("auth_key")
    if not endpoint or not p256dh or not auth:
        return SendResult(status=STATUS_FAILED, error="invalid subscription")

    try:
        # Lazy import — pywebpush pulls in cryptography eagerly, which we
        # already have. Keeps the import surface tight at module load.
        from pywebpush import WebPushException, webpush
    except ImportError as exc:
        logger.error("pywebpush_import_failed", error=str(exc))
        return SendResult(status=STATUS_FAILED, error=f"pywebpush import: {exc}")

    sub_info = {
        "endpoint": endpoint,
        "keys": {"p256dh": p256dh, "auth": auth},
    }

    try:
        response = webpush(
            subscription_info=sub_info,
            data=json.dumps(payload),
            vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ["VAPID_SUBJECT"]},
            ttl=ttl,
        )
        return SendResult(status=STATUS_SENT, http_status=response.status_code)
    except WebPushException as exc:
        http_status = getattr(getattr(exc, "response", None), "status_code", None)
        # 404 + 410 = subscription gone (user unsubscribed at OS level, or
        # uninstalled the PWA). The caller should drop the row.
        if http_status in (404, 410):
            return SendResult(
                status=STATUS_EXPIRED, http_status=http_status, error=str(exc)
            )
        return SendResult(
            status=STATUS_FAILED, http_status=http_status, error=str(exc)
        )
    except Exception as exc:
        return SendResult(status=STATUS_FAILED, error=str(exc))
