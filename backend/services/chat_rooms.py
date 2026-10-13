"""Club-scoped live chat (SB-1330): who may chat in which room.

Each club playing in a match has its own chat room. For IFA vs NEFC, IFA
members chat with IFA members and NEFC members with NEFC members; everyone
still sees the same score, goals and cards. A user whose club is not playing
gets no chat. Admins can read and post in either room and moderate both.

Pure functions only: callers resolve the user's clubs and the match's clubs
from the database and pass them in. The API is the only reader of chat rows
(SB-1329), so the room decided here is the whole of the enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Statuses after which nobody can post. Messages stay readable until the
# 10-day cleanup.
CLOSED_STATUSES = frozenset({"completed", "forfeit", "cancelled", "postponed"})

NOT_A_MEMBER = "Live chat is open to members of the clubs playing"
CHAT_CLOSED = "Chat has closed for this match"


@dataclass(frozen=True)
class ChatRoom:
    club_id: int
    name: str | None


@dataclass(frozen=True)
class ChatAccess:
    """What the viewer can do with this match's chat.

    available: there is a room for this viewer.
    club_id:   the room they read and post in (None when not available).
    rooms:     the rooms they may switch between — both clubs for an admin,
               only their own for anyone else.
    closed:    the match is over; reading is fine, posting is not.
    """

    available: bool
    club_id: int | None
    rooms: list[ChatRoom] = field(default_factory=list)
    closed: bool = False

    @property
    def can_post(self) -> bool:
        return self.available and not self.closed

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "club_id": self.club_id,
            "rooms": [{"club_id": r.club_id, "name": r.name} for r in self.rooms],
            "closed": self.closed,
        }


def match_rooms(
    home_club_id: int | None,
    home_club_name: str | None,
    away_club_id: int | None,
    away_club_name: str | None,
) -> list[ChatRoom]:
    """The match's chat rooms: one per club playing.

    A team with no club has no room. When both teams belong to the same club
    there is a single shared room.
    """
    rooms: list[ChatRoom] = []
    for club_id, name in ((home_club_id, home_club_name), (away_club_id, away_club_name)):
        if club_id is not None and all(r.club_id != club_id for r in rooms):
            rooms.append(ChatRoom(club_id, name))
    return rooms


def is_closed(match_status: str | None, match_end_time: str | None) -> bool:
    return bool(match_end_time) or (match_status or "").lower() in CLOSED_STATUSES


def chat_access(
    *,
    is_admin: bool,
    user_club_ids: list[int],
    rooms: list[ChatRoom],
    closed: bool,
    requested_club_id: int | None = None,
) -> ChatAccess:
    """Decide the viewer's room for one match.

    user_club_ids is in preference order (profile club, then team's club,
    then current roster teams); the first one playing in this match wins.
    requested_club_id is honoured only for admins, who may switch rooms.
    """
    if is_admin:
        if not rooms:
            return ChatAccess(available=False, club_id=None, closed=closed)
        chosen = next((r for r in rooms if r.club_id == requested_club_id), rooms[0])
        return ChatAccess(available=True, club_id=chosen.club_id, rooms=list(rooms), closed=closed)

    by_id = {r.club_id: r for r in rooms}
    for club_id in user_club_ids:
        if club_id in by_id:
            return ChatAccess(available=True, club_id=club_id, rooms=[by_id[club_id]], closed=closed)
    return ChatAccess(available=False, club_id=None, closed=closed)
