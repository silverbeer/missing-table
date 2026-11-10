"""
Scoped notification channels API (SB-1602).

- GET    /api/notification-channels
- GET    /api/notification-channels/event-types
- POST   /api/notification-channels
- PATCH  /api/notification-channels/{id}
- DELETE /api/notification-channels/{id}
- POST   /api/notification-channels/{id}/test

Permissions by scope: global is admin only; a club needs admin or that club's
manager; a squad needs anyone who can manage the team. `destination` is
write-only: responses carry its last four characters as `hint`.
"""

from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.club_notifications import check_rate_limit, ensure_club_access, is_notifications_enabled
from auth import AuthManager, get_current_user_required
from dao.match_dao import SupabaseConnection
from dao.notification_channels_dao import (
    ChannelWriteError,
    DuplicateChannelError,
    NotificationChannelsDAO,
    actor_id,
)
from dao.notification_deliveries_dao import NotificationDeliveriesDAO
from notifications.adapters.base import (
    ChannelAdapter,
    DeliveryError,
    InvalidDestinationError,
    NotificationConfigError,
    UnsupportedPlatformError,
)
from notifications.audience import player_channel_problem
from notifications.preferences import CHANNEL_EVENT_TYPES, EVENT_LABELS, is_player_only
from notifications.registry import get_adapter

logger = structlog.get_logger(__name__)

TEST_MESSAGE = "✅ Missing Table notification test: this channel is set up correctly."

router = APIRouter(prefix="/api/notification-channels", tags=["notification-channels"])

ScopeType = Literal["club", "team", "global"]
Audience = Literal["fans", "players"]

_connection: SupabaseConnection | None = None


def _conn() -> SupabaseConnection:
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return _connection


def _dao() -> NotificationChannelsDAO:
    return NotificationChannelsDAO(_conn())


def _deliveries() -> NotificationDeliveriesDAO:
    return NotificationDeliveriesDAO(_conn())


class ChannelScope(BaseModel):
    scope_type: ScopeType
    club_id: int | None = None
    team_id: int | None = None
    age_group_id: int | None = None


class ChannelCreate(ChannelScope):
    audience: Audience = "fans"
    platform: str
    destination: str = Field(..., min_length=1, max_length=500)
    # None = every event; [] = none. Never collapse the two.
    event_types: list[str] | None = None
    enabled: bool = True
    # Shown to members, unlike destination; see api/channel_members.py.
    invite_url: str | None = Field(None, max_length=500)
    # A manager's own name for the channel; blank is stored as NULL.
    label: str | None = Field(None, max_length=80)


class ChannelUpdate(BaseModel):
    destination: str | None = Field(None, min_length=1, max_length=500)
    event_types: list[str] | None = None
    enabled: bool | None = None
    invite_url: str | None = Field(None, max_length=500)
    # A manager's own name for the channel; blank is stored as NULL.
    label: str | None = Field(None, max_length=80)


class LastDelivery(BaseModel):
    status: Literal["pending", "sent", "failed"]
    at: str | None = None
    # Sanitized when stored: never a destination, token or provider URL.
    error: str | None = None


class TestSendResult(BaseModel):
    success: bool
    error: str | None = None


class EventType(BaseModel):
    id: str
    label: str
    # Only a squad's player channel can carry it (SB-1610).
    player_only: bool = False


class ChannelOut(ChannelScope):
    id: int
    audience: Audience
    platform: str
    event_types: list[str] | None
    enabled: bool
    invite_url: str | None = None
    label: str | None = None
    hint: str | None = Field(None, description="Last 4 chars of destination; full value never exposed")
    # None with last_delivery_known=True: nothing posted yet. With False: the
    # ledger could not be read, so the UI must not claim "nothing yet".
    last_delivery: LastDelivery | None = None
    last_delivery_known: bool = True


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _last_delivery(row: dict | None) -> LastDelivery | None:
    if row is None:
        return None
    return LastDelivery(
        status=row["status"],
        at=row.get("updated_at") or row.get("created_at"),
        error=row.get("error") if row["status"] == "failed" else None,
    )


def _to_out(row: dict, deliveries: dict[int, dict] | None) -> ChannelOut:
    """`deliveries` is latest_for()'s result: None when the ledger was unreadable."""
    destination = row.get("destination") or ""
    return ChannelOut(
        id=row["id"],
        scope_type=row["scope_type"],
        club_id=row.get("club_id"),
        team_id=row.get("team_id"),
        age_group_id=row.get("age_group_id"),
        audience=row["audience"],
        platform=row["platform"],
        event_types=row.get("event_types"),
        enabled=bool(row["enabled"]),
        invite_url=row.get("invite_url"),
        label=row.get("label"),
        hint=destination[-4:] if destination else None,
        last_delivery=_last_delivery((deliveries or {}).get(row["id"])),
        last_delivery_known=deliveries is not None,
    )


def _with_deliveries(rows: list[dict]) -> list[ChannelOut]:
    deliveries = _deliveries().latest_for([row["id"] for row in rows]) if rows else {}
    return [_to_out(row, deliveries) for row in rows]


def _clean_label(fields: dict) -> None:
    """Trim the label in place; blank means none."""
    if "label" in fields and fields["label"] is not None:
        fields["label"] = fields["label"].strip() or None


def _require_scope_shape(scope: ChannelScope) -> None:
    """Exactly the identifiers this scope uses, so the database CHECK is never the first to say so."""
    shape = (scope.club_id is not None, scope.team_id is not None, scope.age_group_id is not None)
    expected = {"club": (True, False, False), "team": (False, True, True), "global": (False, False, False)}
    if shape != expected[scope.scope_type]:
        raise _unprocessable(
            {
                "club": "A club channel needs club_id only",
                "team": "A team channel needs team_id and age_group_id only",
                "global": "A global channel takes no club, team or age group",
            }[scope.scope_type]
        )


def _ensure_scope_access(current_user: dict, scope: ChannelScope) -> None:
    allowed = True
    if scope.scope_type == "global":
        allowed = current_user.get("role") == "admin"
    elif scope.scope_type == "club":
        ensure_club_access(current_user, scope.club_id)
    else:
        allowed = AuthManager(_conn().get_client()).can_manage_team(current_user, scope.team_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to manage this channel")


def _adapter(platform: str) -> ChannelAdapter:
    try:
        return get_adapter(platform)
    except UnsupportedPlatformError:
        raise _unprocessable("Unknown platform") from None


def _validate_destination(adapter: ChannelAdapter, destination: str) -> None:
    try:
        adapter.validate_destination(destination)
    except InvalidDestinationError as exc:
        raise _unprocessable(str(exc)) from None


def _validate_invite_url(adapter: ChannelAdapter, invite_url: str | None) -> None:
    """None clears the link; anything else must be the platform's private join link."""
    if invite_url is None:
        return
    try:
        adapter.validate_invite_url(invite_url)
    except InvalidDestinationError as exc:
        raise _unprocessable(str(exc)) from None


def _validate_event_types(
    event_types: list[str] | None, scope_type: str | None = None, audience: str | None = None
) -> None:
    unknown = sorted(set(event_types or []) - set(CHANNEL_EVENT_TYPES))
    if unknown:
        raise _unprocessable(f"Unknown event types: {', '.join(unknown)}")
    player_only = sorted(e for e in (event_types or []) if is_player_only(e))
    if player_only and (scope_type != "team" or audience != "players"):
        labels = ", ".join(EVENT_LABELS[e] for e in player_only)
        raise _unprocessable(f"{labels} can only go to a squad's player channel")


def _age_group_name(age_group_id: int) -> str:
    rows = _conn().get_client().table("age_groups").select("name").eq("id", age_group_id).limit(1).execute().data
    if not rows:
        raise _unprocessable("Unknown age group")
    return rows[0]["name"]


def _validate_audience(body: ChannelCreate, adapter: ChannelAdapter) -> None:
    if body.scope_type == "global" and body.audience != "fans":
        raise _unprocessable("A global channel is for fans")
    age_group_name = _age_group_name(body.age_group_id) if body.scope_type == "team" else None
    if body.audience == "players":
        problem = player_channel_problem(adapter, age_group_name)
        if problem:
            raise _unprocessable(problem)


@router.get("/event-types", response_model=list[EventType])
def list_event_types(current_user: dict = Depends(get_current_user_required)) -> list[EventType]:
    """The events a channel can be limited to, in display order."""
    return [
        EventType(id=event, label=EVENT_LABELS[event], player_only=is_player_only(event))
        for event in CHANNEL_EVENT_TYPES
    ]


@router.get("", response_model=list[ChannelOut])
def list_channels(
    scope_type: ScopeType,
    club_id: int | None = None,
    team_id: int | None = None,
    age_group_id: int | None = None,
    current_user: dict = Depends(get_current_user_required),
) -> list[ChannelOut]:
    scope = ChannelScope(scope_type=scope_type, club_id=club_id, team_id=team_id, age_group_id=age_group_id)
    _require_scope_shape(scope)
    _ensure_scope_access(current_user, scope)
    return _with_deliveries(_dao().list_for_scope(scope_type, club_id, team_id, age_group_id))


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(
    body: ChannelCreate,
    current_user: dict = Depends(get_current_user_required),
) -> ChannelOut:
    _require_scope_shape(body)
    _ensure_scope_access(current_user, body)
    adapter = _adapter(body.platform)
    _validate_destination(adapter, body.destination)
    _validate_invite_url(adapter, body.invite_url)
    _validate_event_types(body.event_types, body.scope_type, body.audience)
    _validate_audience(body, adapter)
    fields = body.model_dump()
    _clean_label(fields)
    try:
        row = _dao().create({**fields, "created_by": actor_id(current_user)})
    except DuplicateChannelError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That channel already exists") from None
    except ChannelWriteError:
        raise HTTPException(status_code=500, detail="Failed to save notification channel") from None
    # A new channel has posted nothing, so that is known without asking.
    return _to_out(row, {})


def _owned_channel(channel_id: int, current_user: dict) -> dict:
    """The channel, once the caller is cleared for its scope. Absent is 404."""
    row = _dao().get_by_id(channel_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    _ensure_scope_access(
        current_user,
        ChannelScope(
            scope_type=row["scope_type"],
            club_id=row.get("club_id"),
            team_id=row.get("team_id"),
            age_group_id=row.get("age_group_id"),
        ),
    )
    return row


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: int,
    body: ChannelUpdate,
    current_user: dict = Depends(get_current_user_required),
) -> ChannelOut:
    row = _owned_channel(channel_id, current_user)
    # exclude_unset: an explicit `event_types: null` means "every event".
    fields = body.model_dump(exclude_unset=True)
    if fields.get("destination") is not None:
        _validate_destination(_adapter(row["platform"]), fields["destination"])
    elif "destination" in fields:
        raise _unprocessable("destination cannot be null")
    if "enabled" in fields and fields["enabled"] is None:
        raise _unprocessable("enabled cannot be null")
    _validate_event_types(fields.get("event_types"), row["scope_type"], row.get("audience"))
    if "invite_url" in fields:
        _validate_invite_url(_adapter(row["platform"]), fields["invite_url"])
    _clean_label(fields)
    if not fields:
        return _with_deliveries([row])[0]
    try:
        updated = _dao().update(channel_id, fields)
    except DuplicateChannelError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That channel already exists") from None
    except ChannelWriteError:
        raise HTTPException(status_code=500, detail="Failed to save notification channel") from None
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return _with_deliveries([updated])[0]


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user_required),
):
    _owned_channel(channel_id, current_user)
    try:
        _dao().delete_by_id(channel_id)
    except ChannelWriteError:
        raise HTTPException(status_code=500, detail="Failed to delete notification channel") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _test_error(exc: Exception) -> str:
    """What a manager is told. Never a destination, env var or stack detail."""
    if isinstance(exc, DeliveryError):
        return str(exc)
    if isinstance(exc, NotificationConfigError):
        return "This platform is not available on Missing Table right now. Contact support."
    return "The test message could not be sent"


@router.post("/{channel_id}/test", response_model=TestSendResult)
def test_channel(
    channel_id: int,
    current_user: dict = Depends(get_current_user_required),
) -> TestSendResult:
    """Post a test message. Not recorded in the delivery ledger: it is not a match event."""
    row = _owned_channel(channel_id, current_user)
    if not is_notifications_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notifications are turned off on Missing Table right now",
        )
    if not check_rate_limit(f"ratelimit:notify-test:channel:{channel_id}", max_per_minute=5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many test messages. Wait a minute and try again.",
        )
    try:
        _adapter(row["platform"]).send(row["destination"], TEST_MESSAGE)
    except Exception as exc:
        logger.warning("channel_test_send_failed", channel_id=channel_id, error_type=type(exc).__name__)
        return TestSendResult(success=False, error=_test_error(exc))
    return TestSendResult(success=True)
