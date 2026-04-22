"""
Club notification channels API.

Per-club Telegram / Discord destinations for live-match notifications.
- GET    /api/clubs/{club_id}/notifications
- PUT    /api/clubs/{club_id}/notifications/{platform}
- DELETE /api/clubs/{club_id}/notifications/{platform}
- POST   /api/clubs/{club_id}/notifications/{platform}/test

Permissions: admin OR (club_manager AND user_club_id == club_id).
The `destination` value is never returned in full — callers only see the last
four characters of a configured destination as `hint`. The full value stays
write-only from the API's perspective.
"""

from __future__ import annotations

import os
import re
import time
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from auth import get_current_user_required
from dao.club_notifications_dao import VALID_PLATFORMS, ClubNotificationsDAO
from dao.match_dao import SupabaseConnection

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/clubs", tags=["club-notifications"])


# ---------------------------------------------------------------------------
# Connection / DAO (lazy singleton)
# ---------------------------------------------------------------------------

_connection: SupabaseConnection | None = None


def _dao() -> ClubNotificationsDAO:
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return ClubNotificationsDAO(_connection)


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def is_notifications_enabled() -> bool:
    """False only when NOTIFICATIONS_ENABLED is explicitly off."""
    return os.getenv("NOTIFICATIONS_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


# ---------------------------------------------------------------------------
# Redis-backed rate limiter (fail-open)
# ---------------------------------------------------------------------------

_redis_client = None


def _get_redis():
    """Lazy Redis client. Returns None if Redis isn't reachable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, decode_responses=True, socket_timeout=1.0)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("notifications_redis_unavailable", error=str(exc))
        return None


def check_rate_limit(key: str, max_per_minute: int) -> bool:
    """Fixed-window counter. Returns True if the request is allowed.

    Fail-open: any Redis failure returns True so the limiter never takes the
    service down. The limiter is best-effort defense-in-depth, not a hard
    quota.
    """
    client = _get_redis()
    if client is None:
        return True

    bucket = int(time.time() // 60)
    full_key = f"{key}:{bucket}"
    try:
        count = client.incr(full_key)
        if count == 1:
            client.expire(full_key, 65)
        return count <= max_per_minute
    except Exception as exc:
        logger.warning("rate_limit_check_failed", key=key, error=str(exc))
        return True


# ---------------------------------------------------------------------------
# Permission guard
# ---------------------------------------------------------------------------


def ensure_club_access(current_user: dict, club_id: int) -> None:
    """Raise 403 unless the caller is admin or a club_manager for this club."""
    role = current_user.get("role")
    if role == "admin":
        return
    if role == "club_manager" and current_user.get("club_id") == club_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Requires admin or club_manager for this club",
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_TELEGRAM_RE = re.compile(r"^(@\w+|-?\d+)$")
_DISCORD_RE = re.compile(r"^https://discord(app)?\.com/api/webhooks/\d+/[\w-]+$")


def _validate_destination(platform: str, destination: str) -> None:
    if platform == "telegram":
        if not _TELEGRAM_RE.match(destination):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telegram destination must be a numeric chat_id (e.g. -1001234567890) or @channel",
            )
    elif platform == "discord":
        if not _DISCORD_RE.match(destination):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Discord destination must be a webhook URL",
            )


def _validate_platform(platform: str) -> None:
    if platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"platform must be one of {sorted(VALID_PLATFORMS)}",
        )


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class ChannelResponse(BaseModel):
    platform: Literal["telegram", "discord"]
    enabled: bool
    configured: bool
    hint: str | None = Field(None, description="Last 4 chars of destination; full value never exposed")


class ChannelUpsert(BaseModel):
    destination: str = Field(..., min_length=1, max_length=500)
    enabled: bool = True


class TestSendResponse(BaseModel):
    success: bool
    error: str | None = None


def _to_response(row: dict) -> ChannelResponse:
    destination = row.get("destination") or ""
    hint = destination[-4:] if destination else None
    return ChannelResponse(
        platform=row["platform"],
        enabled=bool(row["enabled"]),
        configured=True,
        hint=hint,
    )


# ---------------------------------------------------------------------------
# Test-send stub (Phase 5 replaces this with real Telegram / Discord calls)
# ---------------------------------------------------------------------------


def _send_test_message(platform: str, destination: str) -> None:
    """Send a test notification to verify a destination works.

    Phase 5 wiring: delegates to the notification subsystem's sender helper
    so behavior matches real live-event delivery.
    """
    from notifications.senders import send_to

    send_to(
        platform,
        destination,
        "✅ MissingTable notification test — your channel is configured correctly.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{club_id}/notifications",
    response_model=list[ChannelResponse],
)
def list_channels(
    club_id: int,
    current_user: dict = Depends(get_current_user_required),
) -> list[ChannelResponse]:
    ensure_club_access(current_user, club_id)
    rows = _dao().list_by_club(club_id)
    return [_to_response(row) for row in rows]


@router.put(
    "/{club_id}/notifications/{platform}",
    response_model=ChannelResponse,
)
def upsert_channel(
    club_id: int,
    platform: str,
    body: ChannelUpsert,
    current_user: dict = Depends(get_current_user_required),
) -> ChannelResponse:
    ensure_club_access(current_user, club_id)
    _validate_platform(platform)
    _validate_destination(platform, body.destination)

    row = _dao().upsert(club_id, platform, body.destination, body.enabled)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save notification channel",
        )
    return _to_response(row)


@router.delete(
    "/{club_id}/notifications/{platform}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_channel(
    club_id: int,
    platform: str,
    current_user: dict = Depends(get_current_user_required),
):
    ensure_club_access(current_user, club_id)
    _validate_platform(platform)
    _dao().delete(club_id, platform)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{club_id}/notifications/{platform}/test",
    response_model=TestSendResponse,
)
def test_send_channel(
    club_id: int,
    platform: str,
    current_user: dict = Depends(get_current_user_required),
) -> TestSendResponse:
    ensure_club_access(current_user, club_id)
    _validate_platform(platform)

    if not is_notifications_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notifications are disabled globally (NOTIFICATIONS_ENABLED=false)",
        )

    if not check_rate_limit(f"ratelimit:notify-test:{club_id}", max_per_minute=5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 5 test sends per minute per club",
        )

    row = _dao().get(club_id, platform)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {platform} channel configured for club {club_id}",
        )

    try:
        _send_test_message(platform, row["destination"])
    except Exception as exc:
        logger.exception(
            "test_send_failed",
            club_id=club_id,
            platform=platform,
            error_type=type(exc).__name__,
        )
        return TestSendResponse(success=False, error=type(exc).__name__)

    return TestSendResponse(success=True, error=None)
