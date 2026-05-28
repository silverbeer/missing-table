"""
Web Push notifications API.

User-managed push subscriptions and team follows. Backs SB-51 (slice 5 of
the mobile app epic SB-44).

Endpoints:
- GET    /api/push/vapid-public-key                      — unauthenticated
- POST   /api/users/me/push-subscriptions                — register a device
- GET    /api/users/me/push-subscriptions                — list user's devices
- DELETE /api/users/me/push-subscriptions/{id}           — revoke
- POST   /api/users/me/team-follows                      — follow {team_id}
- GET    /api/users/me/team-follows                      — list follows + team/club
- DELETE /api/users/me/team-follows/{team_id}            — unfollow
- GET    /api/users/me/notification-preferences          — per-event opt-in flags (SB-57)
- PUT    /api/users/me/notification-preferences          — update per-event opt-in flags (SB-57)
- POST   /api/users/me/notifications/test                — send a test push
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from auth import get_current_user_required
from dao.match_dao import SupabaseConnection
from dao.notification_preferences_dao import NotificationPreferencesDAO
from dao.push_send_log_dao import PushSendLogDAO
from dao.push_subscription_dao import PushSubscriptionDAO
from dao.team_follow_dao import TeamFollowDAO
from notifications.preferences import EVENT_TYPES
from notifications.web_push_sender import (
    get_public_key as get_vapid_public_key,
)
from notifications.web_push_sender import (
    is_configured as push_is_configured,
)
from notifications.web_push_sender import (
    send_push,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["push-notifications"])


# ---------------------------------------------------------------------------
# Lazy connection + DAO singletons
# ---------------------------------------------------------------------------

_connection: SupabaseConnection | None = None


def _conn() -> SupabaseConnection:
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return _connection


def _sub_dao() -> PushSubscriptionDAO:
    return PushSubscriptionDAO(_conn())


def _follow_dao() -> TeamFollowDAO:
    return TeamFollowDAO(_conn())


def _log_dao() -> PushSendLogDAO:
    return PushSendLogDAO(_conn())


def _prefs_dao() -> NotificationPreferencesDAO:
    return NotificationPreferencesDAO(_conn())


def _user_id(user: dict[str, Any]) -> str:
    """auth.py's current_user dict uses either 'user_id' or 'id'."""
    uid = user.get("user_id") or user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Missing user identity")
    return str(uid)


# ---------------------------------------------------------------------------
# Rate limiter (reuse the fail-open Redis pattern from club_notifications)
# ---------------------------------------------------------------------------


def _check_test_rate_limit(user_id: str) -> None:
    """10 test sends per minute per user. Fail-open via the existing helper."""
    try:
        from api.club_notifications import check_rate_limit
    except Exception:
        return  # if the helper isn't importable, skip (defense-in-depth)
    if not check_rate_limit(f"push:test:{user_id}", max_per_minute=10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many test notifications — try again in a minute.",
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PushSubscriptionKeys(BaseModel):
    """The two keys returned by the browser's PushManager.subscribe()."""

    p256dh: str = Field(..., min_length=1, max_length=200)
    auth: str = Field(..., min_length=1, max_length=100)


class PushSubscriptionIn(BaseModel):
    """Body of POST /api/users/me/push-subscriptions."""

    endpoint: str = Field(..., min_length=1, max_length=2000)
    keys: PushSubscriptionKeys
    device_label: str | None = Field(None, max_length=100)
    user_agent: str | None = Field(None, max_length=500)


class TeamFollowIn(BaseModel):
    """Body of POST /api/users/me/team-follows."""

    team_id: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Public: VAPID public key (no auth)
# ---------------------------------------------------------------------------


@router.get("/push/vapid-public-key")
def get_vapid_public_key_endpoint() -> dict[str, str]:
    """Return the VAPID public key the browser needs to subscribe.

    Public information — no authentication required. Returns 503 if the
    backend isn't configured for push yet (SB-50 hasn't landed).
    """
    if not push_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured on this server.",
        )
    key = get_vapid_public_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VAPID public key not available.",
        )
    return {"publicKey": key}


# ---------------------------------------------------------------------------
# Push subscriptions
# ---------------------------------------------------------------------------


@router.post(
    "/users/me/push-subscriptions",
    status_code=status.HTTP_201_CREATED,
)
def register_subscription(
    payload: PushSubscriptionIn,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Register (or update) a push subscription for the current user."""
    user_id = _user_id(current_user)
    row = _sub_dao().upsert(
        user_id=user_id,
        endpoint=payload.endpoint,
        p256dh_key=payload.keys.p256dh,
        auth_key=payload.keys.auth,
        device_label=payload.device_label,
        user_agent=payload.user_agent,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register push subscription.",
        )
    # Never echo the keys back — they're write-only from the API's view.
    return {
        "id": row.get("id"),
        "device_label": row.get("device_label"),
        "created_at": row.get("created_at"),
        "last_seen_at": row.get("last_seen_at"),
    }


@router.get("/users/me/push-subscriptions")
def list_subscriptions(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, list[dict]]:
    user_id = _user_id(current_user)
    return {"subscriptions": _sub_dao().list_by_user(user_id)}


@router.delete(
    "/users/me/push-subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_subscription(
    subscription_id: str,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> Response:
    user_id = _user_id(current_user)
    deleted = _sub_dao().delete_by_id(user_id, subscription_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Team follows
# ---------------------------------------------------------------------------


@router.post(
    "/users/me/team-follows",
    status_code=status.HTTP_201_CREATED,
)
def follow_team(
    payload: TeamFollowIn,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    user_id = _user_id(current_user)
    ok = _follow_dao().follow(user_id, payload.team_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to follow team.",
        )
    return {"team_id": payload.team_id, "following": True}


@router.get("/users/me/team-follows")
def list_team_follows(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, list[dict]]:
    user_id = _user_id(current_user)
    return {"follows": _follow_dao().list_for_user(user_id)}


@router.delete(
    "/users/me/team-follows/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unfollow_team(
    team_id: int,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> Response:
    user_id = _user_id(current_user)
    _follow_dao().unfollow(user_id, team_id)  # idempotent
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Notification preferences (SB-57)
# ---------------------------------------------------------------------------


class NotificationPreferencesIn(BaseModel):
    """Body of PUT /api/users/me/notification-preferences."""

    preferences: dict[str, bool] = Field(
        ...,
        description=(
            "Map of event_type → enabled. Unknown event types are ignored. "
            f"Known event types: {', '.join(EVENT_TYPES)}."
        ),
    )


@router.get("/users/me/notification-preferences")
def get_notification_preferences(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, dict[str, bool]]:
    user_id = _user_id(current_user)
    return {"preferences": _prefs_dao().get_preferences(user_id)}


@router.put("/users/me/notification-preferences")
def update_notification_preferences(
    payload: NotificationPreferencesIn,
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, dict[str, bool]]:
    # Reject unknown event types up front rather than silently dropping them —
    # surfaces client bugs faster.
    unknown = [k for k in payload.preferences if k not in EVENT_TYPES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown event types: {', '.join(unknown)}",
        )
    user_id = _user_id(current_user)
    merged = _prefs_dao().set_preferences(user_id, payload.preferences)
    return {"preferences": merged}


# ---------------------------------------------------------------------------
# Test notification
# ---------------------------------------------------------------------------


@router.post("/users/me/notifications/test")
def send_test_notification(
    current_user: dict[str, Any] = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Fire a test push to all of the current user's subscriptions.

    Useful for verifying setup end-to-end after enabling notifications.
    Rate limited 10/min per user.
    """
    user_id = _user_id(current_user)
    _check_test_rate_limit(user_id)

    if not push_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured on this server.",
        )

    subs = _sub_dao().list_by_user(user_id)
    # list_by_user doesn't return keys; we need the full row for sending.
    # Fetch fresh from the table including keys.
    try:
        full_rows = (
            _conn()
            .get_client()
            .table("push_subscriptions")
            .select("id, endpoint, p256dh_key, auth_key")
            .eq("user_id", user_id)
            .execute()
        )
        full_subs = full_rows.data or []
    except Exception:
        logger.exception("test_push_fetch_subs_failed", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load subscriptions.",
        ) from None

    if not full_subs:
        return {"sent": 0, "failed": 0, "subscriptions": 0}

    payload = {
        "title": "✅ Missing Table — test notification",
        "body": "Push notifications are working on this device.",
        "icon": "/pwa/icon-192.png",
        "badge": "/pwa/icon-192.png",
        "tag": "mt-test",
        "data": {"url": "/", "test": True},
    }

    sent = 0
    failed = 0
    expired = 0
    log_dao = _log_dao()
    sub_dao = _sub_dao()
    for sub in full_subs:
        result = send_push(sub, payload)
        log_dao.log(
            subscription_id=sub.get("id"),
            user_id=user_id,
            match_id=None,
            event_type="test",
            status=result.status,
            http_status=result.http_status,
            error=result.error,
        )
        if result.ok:
            sent += 1
        elif result.expired:
            expired += 1
            sub_dao.delete_by_endpoint(sub["endpoint"])
        else:
            failed += 1

    # subscription count BEFORE we removed expired ones (for the UI summary)
    return {
        "sent": sent,
        "failed": failed,
        "expired": expired,
        "subscriptions": len(subs),
    }
