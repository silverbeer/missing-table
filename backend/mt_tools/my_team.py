"""Which team is "mine" (SB-1317): the one place a caller's team membership is read.

Today membership is the caller's profile — `team_id`, or `club_id` alone for club
managers and club fans. This is the one place my-tier and team-write tools read
membership. auth.py's `can_manage_team` reads the profile itself, and must change
together with this module when membership moves to its own table (SB-1319). A
team-write tool still re-checks the resolved team with `can_manage_team` before it
writes: knowing your team is not permission to edit it.

Most callers have no team, and that is a normal answer (`no_team`), not an error.
A profile pointing at a team or club that no longer exists — or one this viewer
may not see — is logged and skipped: a dead `team_id` falls back to `club_id`,
and with nothing left the answer is `no_team`. A failed read is `unavailable`,
never `no_team`: "MT could not check" must not read as "you have no team".

Visibility is search_teams': the same team index, so a test team never reaches a
real viewer through here either.
"""

from typing import Any, Literal

import structlog
from pydantic import BaseModel

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import TeamCandidate, ToolError, Viewer
from mt_ai.tools.visibility import TeamIndex, load_team_index

logger = structlog.get_logger()


class ClubRef(BaseModel):
    id: int
    name: str


class MyTeamResult(BaseModel):
    """The caller's team, their club's teams, or neither.

    `teams` is one entry per age group a team plays in (as search_teams returns
    them): the caller's team for `team`, every team of the club for `club`, and
    null for `no_team` or when the read failed. [] means none this viewer can
    see: a club with no teams, or a team that plays in no competition the viewer
    can see (all its registrations are test content).
    """

    status: Literal["team", "club", "no_team"] | None = None
    team_id: int | None = None
    club: ClubRef | None = None
    teams: list[TeamCandidate] | None = None
    error: ToolError | None = None


def resolve_my_team(deps: ToolDeps, user: dict[str, Any], viewer: Viewer) -> MyTeamResult:
    """The caller's team from their profile (`team_id`, else `club_id`)."""
    team_id = user.get("team_id")
    club_id = user.get("club_id")
    if team_id is None and club_id is None:
        return MyTeamResult(status="no_team")

    try:
        index = load_team_index(deps, viewer)
    except Exception:
        logger.exception("resolve_my_team failed", user_id=user.get("user_id"))
        return MyTeamResult(error=ToolError(kind="unavailable", message="Your team is unavailable right now."))

    if team_id is not None:
        team = index.teams.get(team_id)
        if team is not None:
            return MyTeamResult(
                status="team",
                team_id=team_id,
                club=_club_ref(index, team.get("club_id")),
                teams=index.candidates(team),
            )
        logger.warning("my_team_dangling", user_id=user.get("user_id"), team_id=team_id)

    if club_id is None:
        return MyTeamResult(status="no_team")
    club = _club_ref(index, club_id)
    if club is None:
        logger.warning("my_club_dangling", user_id=user.get("user_id"), club_id=club_id)
        return MyTeamResult(status="no_team")
    teams = sorted(
        (t for t in index.teams.values() if t.get("club_id") == club_id), key=lambda t: (t.get("name") or "", t["id"])
    )
    return MyTeamResult(status="club", club=club, teams=[c for t in teams for c in index.candidates(t)])


def _club_ref(index: TeamIndex, club_id: int | None) -> ClubRef | None:
    club = index.visible_club(club_id)
    return ClubRef(id=club["id"], name=club["name"]) if club else None
