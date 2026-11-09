"""
Channel access API (SB-1607): who may join which notification channel.

- GET    /api/teams/{team_id}/channels/available     what the caller may see, always 200
- GET    /api/me/channels[?team_id=]                  the same, with what the profile card needs
- POST   /api/channels/{channel_id}/join             join a channel the caller is entitled to
- POST   /api/channels/{channel_id}/request          ask a manager for access
- DELETE /api/channels/{channel_id}/request          withdraw a pending request
- GET    /api/channels/requests?team_id=             pending requests a manager may decide
- PUT    /api/channels/{channel_id}/members/{user_id} approve, deny, invite or revoke

The rules are in `notifications/membership.py`; the caller's standing comes from
`mt_tools/my_team.py`. A channel the caller may not see is 404, never 403, so a
fan cannot learn that a player channel exists. `destination` is never read here,
and `invite_url` is returned only to an active member who is still eligible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from api.notification_channels import ChannelScope, _ensure_scope_access
from auth import get_current_user_required
from dao.channel_members_dao import ChannelMembersDAO, MemberWriteError
from dao.match_dao import SupabaseConnection
from dao.notification_channels_dao import actor_id
from mt_tools.my_team import ChannelViewer, channel_viewer
from notifications.adapters.base import UnsupportedPlatformError
from notifications.membership import (
    Access,
    ChannelFacts,
    State,
    can_be_granted,
    channel_access,
    viewer_state,
)
from notifications.registry import get_adapter

router = APIRouter(prefix="/api", tags=["channel-access"])

_connection: SupabaseConnection | None = None


def _dao() -> ChannelMembersDAO:
    global _connection
    if _connection is None:
        _connection = SupabaseConnection()
    return ChannelMembersDAO(_connection)


class AvailableChannel(BaseModel):
    id: int
    scope_type: str
    audience: str
    platform: str
    platform_label: str
    team_id: int | None
    age_group_id: int | None
    age_group_name: str | None
    state: State
    invite_url: str | None = None


class MyChannels(BaseModel):
    """What the profile card renders (SB-1609).

    `has_team`: the caller has a team or club to have channels for.
    `managed`: someone on MT manages that team or club (the claimed state);
    None when that could not be checked.
    `can_manage`: the caller manages it, so an empty card offers setup.
    """

    channels: list[AvailableChannel]
    has_team: bool
    managed: bool | None
    can_manage: bool


class MemberDecision(BaseModel):
    status: Literal["active", "denied", "revoked"]


class MemberOut(BaseModel):
    channel_id: int
    user_id: str
    status: str
    source: str


class PendingRequest(BaseModel):
    channel_id: int
    user_id: str
    display_name: str | None
    requested_at: str | None
    platform: str
    audience: str
    age_group_name: str | None


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")


def _caller_id(current_user: dict) -> str:
    user_id = actor_id(current_user)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a signed-in user can join channels")
    return user_id


def _viewer(dao: ChannelMembersDAO, user: dict, user_id: str) -> ChannelViewer:
    team_club = dao.team_club_id(user.get("team_id")) if user.get("club_id") is None else None
    squads = dao.current_squads(user_id) if (user.get("role") or "").replace("_", "-") == "team-player" else []
    return channel_viewer(user, team_club, squads)


def _facts(dao: ChannelMembersDAO, row: dict, names: dict[int, str] | None = None) -> ChannelFacts:
    club_id = row.get("club_id") if row["scope_type"] != "team" else dao.team_club_id(row.get("team_id"))
    age_group_id = row.get("age_group_id")
    if names is None:
        names = dao.age_group_names({age_group_id} if age_group_id else set())
    return ChannelFacts(
        scope_type=row["scope_type"],
        audience=row["audience"],
        club_id=club_id,
        team_id=row.get("team_id"),
        age_group_id=age_group_id,
        age_group_name=names.get(age_group_id) if age_group_id else None,
    )


def _joinable_link(row: dict) -> bool:
    """Only an enabled channel with an invite link can be joined."""
    return bool(row.get("enabled")) and bool(row.get("invite_url"))


def _label(platform: str) -> str:
    try:
        return get_adapter(platform).label
    except UnsupportedPlatformError:
        return platform


def _to_available(row: dict, facts: ChannelFacts, state: State) -> AvailableChannel:
    return AvailableChannel(
        id=row["id"],
        scope_type=row["scope_type"],
        audience=row["audience"],
        platform=row["platform"],
        platform_label=_label(row["platform"]),
        team_id=row.get("team_id"),
        age_group_id=row.get("age_group_id"),
        age_group_name=facts.age_group_name,
        state=state,
        invite_url=row["invite_url"] if state == "member" else None,
    )


def _visible_channel(
    dao: ChannelMembersDAO, channel_id: int, viewer: ChannelViewer
) -> tuple[dict, ChannelFacts, Access]:
    """The channel and the caller's access, or 404 when they may not see it."""
    row = dao.channel(channel_id)
    if row is None or not _joinable_link(row):
        raise _not_found()
    facts = _facts(dao, row)
    access = channel_access(viewer, facts)
    if access == "hidden":
        raise _not_found()
    return row, facts, access


def _now() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/teams/{team_id}/channels/available", response_model=list[AvailableChannel])
def available_channels(team_id: int, current_user: dict = Depends(get_current_user_required)) -> list[AvailableChannel]:
    """The team's squad channels and its club's channels this caller may see.

    An unknown team, a team with no channels, or channels without an invite link
    all answer 200 with an empty list.
    """
    dao = _dao()
    user_id = actor_id(current_user)
    viewer = _viewer(dao, current_user, user_id) if user_id else channel_viewer(current_user, None, [])
    clubs = dao.team_clubs({team_id})
    club_id = clubs.get(team_id)
    return _visible(dao, viewer, user_id, dao.channels_for_team(team_id, club_id), clubs)


def _visible(
    dao: ChannelMembersDAO, viewer: ChannelViewer, user_id: str | None, rows: list[dict], clubs: dict[int, int | None]
) -> list[AvailableChannel]:
    """The rows this viewer may see, with their state. `clubs` maps team id to club id."""
    rows = [r for r in rows if _joinable_link(r)]
    names = dao.age_group_names({r["age_group_id"] for r in rows if r.get("age_group_id")})
    statuses = dao.statuses(user_id, [r["id"] for r in rows]) if user_id else {}
    out: list[AvailableChannel] = []
    for row in rows:
        facts = ChannelFacts(
            scope_type=row["scope_type"],
            audience=row["audience"],
            club_id=row.get("club_id") if row["scope_type"] == "club" else clubs.get(row.get("team_id")),
            team_id=row.get("team_id"),
            age_group_id=row.get("age_group_id"),
            age_group_name=names.get(row.get("age_group_id")),
        )
        state = viewer_state(channel_access(viewer, facts), statuses.get(row["id"]))
        if state is not None:
            out.append(_to_available(row, facts, state))
    return out


@router.get("/me/channels", response_model=MyChannels)
def my_channels(team_id: int | None = None, current_user: dict = Depends(get_current_user_required)) -> MyChannels:
    """Channels for the caller's own teams and club, or for `team_id` (the My Club page)."""
    dao = _dao()
    user_id = actor_id(current_user)
    viewer = _viewer(dao, current_user, user_id) if user_id else channel_viewer(current_user, None, [])
    if team_id is not None:
        team_ids = {team_id}
        clubs = dao.team_clubs(team_ids)
        club_ids = {c for c in clubs.values() if c is not None}
        can_manage = _can_manage(current_user, {"scope_type": "team", "team_id": team_id})
    else:
        team_ids = {t for t in [current_user.get("team_id"), *(s.team_id for s in viewer.squads)] if t is not None}
        clubs = dao.team_clubs(team_ids)
        club_ids = {c for c in [viewer.club_id, *clubs.values(), *(s.club_id for s in viewer.squads)] if c is not None}
        can_manage = viewer.kind == "admin" or (
            viewer.kind in ("club_manager", "team_manager") and bool(team_ids or club_ids)
        )
    if not team_ids and not club_ids:
        return MyChannels(channels=[], has_team=False, managed=None, can_manage=False)
    rows = dao.channels_for_teams(team_ids, club_ids)
    return MyChannels(
        channels=_visible(dao, viewer, user_id, rows, clubs),
        has_team=True,
        managed=dao.is_managed(team_ids, club_ids),
        can_manage=can_manage,
    )


@router.post("/channels/{channel_id}/join", response_model=AvailableChannel)
def join_channel(channel_id: int, current_user: dict = Depends(get_current_user_required)) -> AvailableChannel:
    dao = _dao()
    user_id = _caller_id(current_user)
    row, facts, access = _visible_channel(dao, channel_id, _viewer(dao, current_user, user_id))
    existing = dao.get(channel_id, user_id)
    if existing and existing["status"] in ("denied", "revoked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ask a manager about this channel")
    if access != "joinable":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This channel needs a manager's approval")
    if not existing or existing["status"] != "active":
        try:
            dao.save(channel_id, user_id, {"status": "active", "source": "eligible", "decided_at": _now()})
        except MemberWriteError:
            raise HTTPException(status_code=500, detail="Could not join the channel") from None
    return _to_available(row, facts, "member")


@router.post("/channels/{channel_id}/request", response_model=AvailableChannel)
def request_channel(channel_id: int, current_user: dict = Depends(get_current_user_required)) -> AvailableChannel:
    dao = _dao()
    user_id = _caller_id(current_user)
    row, facts, access = _visible_channel(dao, channel_id, _viewer(dao, current_user, user_id))
    existing = dao.get(channel_id, user_id)
    current = existing["status"] if existing else None
    if current in ("denied", "revoked"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ask a manager about this channel")
    if current in ("requested", "active"):
        return _to_available(row, facts, viewer_state(access, current))
    if access != "requestable":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can join this channel directly")
    try:
        dao.save(channel_id, user_id, {"status": "requested", "source": "request"})
    except MemberWriteError:
        raise HTTPException(status_code=500, detail="Could not send the request") from None
    return _to_available(row, facts, "requested")


@router.delete("/channels/{channel_id}/request", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def withdraw_request(channel_id: int, current_user: dict = Depends(get_current_user_required)):
    dao = _dao()
    user_id = _caller_id(current_user)
    existing = dao.get(channel_id, user_id)
    if not existing or existing["status"] != "requested":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending request")
    try:
        dao.delete(channel_id, user_id)
    except MemberWriteError:
        raise HTTPException(status_code=500, detail="Could not withdraw the request") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _scope(row: dict) -> ChannelScope:
    return ChannelScope(
        scope_type=row["scope_type"],
        club_id=row.get("club_id"),
        team_id=row.get("team_id"),
        age_group_id=row.get("age_group_id"),
    )


def _can_manage(current_user: dict, row: dict) -> bool:
    try:
        _ensure_scope_access(current_user, _scope(row))
    except HTTPException:
        return False
    return True


@router.get("/channels/requests", response_model=list[PendingRequest])
def pending_requests(team_id: int, current_user: dict = Depends(get_current_user_required)) -> list[PendingRequest]:
    """Requests on this team's channels that the caller manages. Team managers included."""
    dao = _dao()
    rows = [r for r in dao.channels_for_team(team_id, dao.team_club_id(team_id)) if _can_manage(current_user, r)]
    if not rows:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to review this team's channels")
    by_id = {r["id"]: r for r in rows}
    names = dao.age_group_names({r["age_group_id"] for r in rows if r.get("age_group_id")})
    out = []
    for req in dao.requested(list(by_id)):
        channel = by_id[req["channel_id"]]
        profile = req.get("user_profiles") or {}
        out.append(
            PendingRequest(
                channel_id=req["channel_id"],
                user_id=req["user_id"],
                display_name=profile.get("display_name") or profile.get("username"),
                requested_at=req.get("created_at"),
                platform=channel["platform"],
                audience=channel["audience"],
                age_group_name=names.get(channel.get("age_group_id")),
            )
        )
    return out


@router.put("/channels/{channel_id}/members/{user_id}", response_model=MemberOut)
def decide_member(
    channel_id: int,
    user_id: str,
    body: MemberDecision,
    current_user: dict = Depends(get_current_user_required),
) -> MemberOut:
    """Approve or deny a request, invite someone, or revoke access.

    `active` without a request is a manager invite. Either way the person must
    already be allowed to ask or join: no manager can put a fan in a player channel.
    """
    dao = _dao()
    row = dao.channel(channel_id)
    if row is None:
        raise _not_found()
    _ensure_scope_access(current_user, _scope(row))

    existing = dao.get(channel_id, user_id)
    current = existing["status"] if existing else None
    fields = {"status": body.status, "decided_by": actor_id(current_user), "decided_at": _now()}

    if body.status == "active":
        profile = dao.profile(user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        target = _viewer(dao, profile, user_id)
        if not can_be_granted(channel_access(target, _facts(dao, row))):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This person can't be given access to this channel",
            )
        fields["source"] = existing["source"] if current == "requested" else "invite"
    elif body.status == "denied":
        if current != "requested":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There is no pending request to deny")
        fields["source"] = existing["source"]
    else:
        if current != "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This person has no access to revoke")
        fields["source"] = existing["source"]

    try:
        saved = dao.save(channel_id, user_id, fields)
    except MemberWriteError:
        raise HTTPException(status_code=500, detail="Could not save channel access") from None
    return MemberOut(channel_id=channel_id, user_id=user_id, status=saved["status"], source=saved["source"])
