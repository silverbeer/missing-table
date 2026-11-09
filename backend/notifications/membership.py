"""Who may see and join a notification channel (SB-1607). Pure: no IO.

A channel is visible to a viewer as one of:

- `joinable`: their club or squad entitles them; joining needs no approval.
- `requestable`: they may ask, and a manager decides (a fan and their club's
  squad fan channel).
- `hidden`: they may not know it exists.

Rules:

- Players see only player channels, and only for a squad they are currently on
  (or their club's, for a club player channel), at U14 and above.
- Fans never see player channels. A club fan channel is joinable by the club's
  fans; a squad fan channel is requested.
- Managers may join the channels of what they manage; team managers also join
  their club's fan channel, since it is their My Club.
- Global channels are never listed: they are the operator's feed.

A grant (`channel_members` row) is not enough on its own. The invite link is
shown only while the viewer is still not `hidden`, so a player who leaves a
squad loses the link without anyone revoking anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from notifications.audience import players_allowed_at

if TYPE_CHECKING:
    from mt_tools.my_team import ChannelViewer

Access = Literal["hidden", "requestable", "joinable"]
MemberStatus = Literal["requested", "active", "denied", "revoked"]


@dataclass(frozen=True)
class ChannelFacts:
    """What the rules need about a channel. `club_id` is its own club, or its team's."""

    scope_type: str
    audience: str
    club_id: int | None
    team_id: int | None = None
    age_group_id: int | None = None
    age_group_name: str | None = None


def channel_access(viewer: ChannelViewer, channel: ChannelFacts) -> Access:
    if channel.scope_type not in ("club", "team"):
        return "hidden"
    if viewer.kind == "admin":
        return "joinable"
    if channel.audience == "players":
        return _player_channel(viewer, channel)
    return _fan_channel(viewer, channel)


def manages(viewer: ChannelViewer, channel: ChannelFacts) -> bool:
    if viewer.kind == "club_manager":
        return viewer.club_id is not None and viewer.club_id == channel.club_id
    if viewer.kind == "team_manager":
        return channel.scope_type == "team" and viewer.team_id is not None and viewer.team_id == channel.team_id
    return False


def _player_channel(viewer: ChannelViewer, channel: ChannelFacts) -> Access:
    if channel.scope_type == "team" and not players_allowed_at(channel.age_group_name):
        return "hidden"
    if manages(viewer, channel):
        return "joinable"
    if viewer.kind != "player":
        return "hidden"
    for squad in viewer.squads:
        if not players_allowed_at(squad.age_group_name):
            continue
        if channel.scope_type == "team" and (squad.team_id, squad.age_group_id) == (
            channel.team_id,
            channel.age_group_id,
        ):
            return "joinable"
        if channel.scope_type == "club" and squad.club_id is not None and squad.club_id == channel.club_id:
            return "joinable"
    return "hidden"


def _fan_channel(viewer: ChannelViewer, channel: ChannelFacts) -> Access:
    if viewer.kind == "player":
        return "hidden"
    if manages(viewer, channel):
        return "joinable"
    same_club = viewer.club_id is not None and viewer.club_id == channel.club_id
    if channel.scope_type == "club":
        return "joinable" if same_club and viewer.kind in ("fan", "team_manager") else "hidden"
    return "requestable" if same_club and viewer.kind == "fan" else "hidden"


State = Literal["can_join", "can_request", "requested", "member", "denied", "revoked"]


def viewer_state(access: Access, status: MemberStatus | None) -> State | None:
    """What the viewer sees for a channel; None when it is hidden from them."""
    if access == "hidden":
        return None
    if status == "active":
        return "member"
    if status in ("requested", "denied", "revoked"):
        return status
    return "can_join" if access == "joinable" else "can_request"


def can_be_granted(target_access: Access) -> bool:
    """A manager can only grant access to someone the rules already allow to ask or join."""
    return target_access != "hidden"
