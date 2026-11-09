"""
Scoped notification channels API (SB-1602).

- GET    /api/notification-channels
- POST   /api/notification-channels
- PATCH  /api/notification-channels/{id}
- DELETE /api/notification-channels/{id}

Permissions by scope: global is admin only; a club needs admin or that club's
manager; a squad needs anyone who can manage the team. `destination` is
write-only: responses carry its last four characters as `hint`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.club_notifications import ensure_club_access
from auth import AuthManager, get_current_user_required
from dao.match_dao import SupabaseConnection
from dao.notification_channels_dao import (
    ChannelWriteError,
    DuplicateChannelError,
    NotificationChannelsDAO,
    actor_id,
)
from notifications.adapters.base import ChannelAdapter, InvalidDestinationError, UnsupportedPlatformError
from notifications.audience import player_channel_problem
from notifications.preferences import EVENT_TYPES
from notifications.registry import get_adapter

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


class ChannelUpdate(BaseModel):
    destination: str | None = Field(None, min_length=1, max_length=500)
    event_types: list[str] | None = None
    enabled: bool | None = None
    invite_url: str | None = Field(None, max_length=500)


class ChannelOut(ChannelScope):
    id: int
    audience: Audience
    platform: str
    event_types: list[str] | None
    enabled: bool
    invite_url: str | None = None
    hint: str | None = Field(None, description="Last 4 chars of destination; full value never exposed")


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _to_out(row: dict) -> ChannelOut:
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
        hint=destination[-4:] if destination else None,
    )


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


def _validate_event_types(event_types: list[str] | None) -> None:
    unknown = sorted(set(event_types or []) - set(EVENT_TYPES))
    if unknown:
        raise _unprocessable(f"Unknown event types: {', '.join(unknown)}")


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
    return [_to_out(row) for row in _dao().list_for_scope(scope_type, club_id, team_id, age_group_id)]


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
    _validate_event_types(body.event_types)
    _validate_audience(body, adapter)
    try:
        row = _dao().create({**body.model_dump(), "created_by": actor_id(current_user)})
    except DuplicateChannelError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That channel already exists") from None
    except ChannelWriteError:
        raise HTTPException(status_code=500, detail="Failed to save notification channel") from None
    return _to_out(row)


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
    _validate_event_types(fields.get("event_types"))
    if "invite_url" in fields:
        _validate_invite_url(_adapter(row["platform"]), fields["invite_url"])
    if not fields:
        return _to_out(row)
    try:
        updated = _dao().update(channel_id, fields)
    except DuplicateChannelError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That channel already exists") from None
    except ChannelWriteError:
        raise HTTPException(status_code=500, detail="Failed to save notification channel") from None
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return _to_out(updated)


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
