"""Ask the MT API to send a final-score alert after the worker writes a score (SB-1619).

The worker writes scores straight to the database, so the API's own
write-path alert never runs for scraped scores. The worker also has none of
the push credentials (web push, APNs, FCM), which live only with the API.
So after a write that sets a new final score, it calls
POST /api/matches/{id}/final-score-alert, and the API decides and sends.

Best-effort by design: an alert that cannot be requested is logged and
dropped. It never fails, delays or retries the ingest of the score itself.

Needs MT_API_URL (the API's base URL) and SERVICE_ACCOUNT_SECRET (the same
secret the API verifies service tokens with). Without either it stays dormant.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from logging_config import get_logger
from notifications.score_change import is_new_final_score

logger = get_logger(__name__)

SERVICE_NAME = "match-scraper-worker"
TOKEN_TTL = timedelta(minutes=5)
REQUEST_TIMEOUT_SECONDS = 5.0


def service_token(secret: str, now: datetime | None = None) -> str:
    """A short-lived service-account token the API accepts (auth.verify_service_account_token)."""
    issued = now or datetime.now(UTC)
    payload = {
        "sub": f"service-{SERVICE_NAME}",
        "iss": "missing-table",
        "aud": "service-account",
        "iat": int(issued.timestamp()),
        "exp": int((issued + TOKEN_TTL).timestamp()),
        "service_name": SERVICE_NAME,
        "permissions": ["manage_matches"],
        "role": "service_account",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def alert_if_new_final_score(before: dict[str, Any] | None, after: dict[str, Any], post=None) -> bool:
    """Request the alert when the write set a new final score. Returns whether it asked.

    The API re-checks everything (completed, both scores, recent, not already
    sent), so this only avoids calling it for writes that changed no score.
    """
    if not is_new_final_score(before, after):
        return False
    match_id = after.get("id")
    base = (os.getenv("MT_API_URL") or "").rstrip("/")
    secret = os.getenv("SERVICE_ACCOUNT_SECRET") or ""
    if match_id is None or not base or not secret:
        logger.warning("final_score_alert_dormant", match_id=match_id, has_url=bool(base), has_secret=bool(secret))
        return False
    send = post or httpx.post
    try:
        response = send(
            f"{base}/api/matches/{match_id}/final-score-alert",
            headers={"Authorization": f"Bearer {service_token(secret)}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        status = getattr(response, "status_code", None)
        if status != 200:
            logger.warning("final_score_alert_rejected", match_id=match_id, http_status=status)
        else:
            body = response.json()
            logger.info(
                "final_score_alert_requested",
                match_id=match_id,
                queued=body.get("queued"),
                reason=body.get("reason"),
            )
    except Exception as exc:
        logger.warning("final_score_alert_failed", match_id=match_id, error_type=type(exc).__name__)
    return True
