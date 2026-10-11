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

Active (SB-1322) means the team has at least one match in the current season.
It is derived from scraped fixtures, never flagged: nothing to maintain, and a
team that returns next season comes back on its own. A club lists only its
active teams unless `include_inactive`, and says how many it hid. A caller's own
team is always returned, marked inactive if it is: it is still their team. No
current season, or a failed activity read, is `unavailable` — never "everything
inactive".
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
    them): the caller's team for `team`, the club's teams for `club`, and null
    for `no_team` or when the read failed. Each entry carries `active`.

    A club lists its active teams only, unless include_inactive; `inactive_hidden`
    counts the teams (not entries) left out, and is 0 when nothing was. So
    `teams: []` with `inactive_hidden: 7` is a club with seven teams and none
    playing this season (August, before schedules load), while `teams: []` with
    `inactive_hidden: 0` is a club with nothing to show: no teams, or none this
    viewer can see. A `team` caller's [] means their team plays in no
    competition the viewer can see (all its registrations are test content).

    `season` is the current season's name, the season "active" was judged on.
    It and `inactive_hidden` are null for `no_team` and on error.
    """

    status: Literal["team", "club", "no_team"] | None = None
    team_id: int | None = None
    club: ClubRef | None = None
    teams: list[TeamCandidate] | None = None
    season: str | None = None
    inactive_hidden: int | None = None
    error: ToolError | None = None


class _NoCurrentSeason(Exception):
    """No season is current: activity cannot be judged, so nothing is called inactive."""


UNAVAILABLE = "Your team is unavailable right now."


def resolve_my_team(
    deps: ToolDeps, user: dict[str, Any], viewer: Viewer, include_inactive: bool = False
) -> MyTeamResult:
    """The caller's team from their profile (`team_id`, else `club_id`)."""
    team_id = user.get("team_id")
    club_id = user.get("club_id")
    if team_id is None and club_id is None:
        return MyTeamResult(status="no_team")

    try:
        return _resolve(deps, user, viewer, team_id, club_id, include_inactive)
    except _NoCurrentSeason:
        logger.warning("my_team_no_current_season", user_id=user.get("user_id"))
    except Exception:
        logger.exception("resolve_my_team failed", user_id=user.get("user_id"))
    return MyTeamResult(error=ToolError(kind="unavailable", message=UNAVAILABLE))


def _resolve(
    deps: ToolDeps,
    user: dict[str, Any],
    viewer: Viewer,
    team_id: int | None,
    club_id: int | None,
    include_inactive: bool,
) -> MyTeamResult:
    index = load_team_index(deps, viewer)

    if team_id is not None:
        team = index.teams.get(team_id)
        if team is not None:
            season = _current_season(deps)
            active = deps.matches.team_has_matches_in_season(team_id, season["id"], viewer.include_test)
            return MyTeamResult(
                status="team",
                team_id=team_id,
                club=_club_ref(index, team.get("club_id")),
                teams=_marked(index, team, active),
                season=season.get("name"),
                inactive_hidden=0,
            )
        logger.warning("my_team_dangling", user_id=user.get("user_id"), team_id=team_id)

    if club_id is None:
        return MyTeamResult(status="no_team")
    club = _club_ref(index, club_id)
    if club is None:
        logger.warning("my_club_dangling", user_id=user.get("user_id"), club_id=club_id)
        return MyTeamResult(status="no_team")
    season = _current_season(deps)
    teams = sorted(
        (t for t in index.teams.values() if t.get("club_id") == club_id), key=lambda t: (t.get("name") or "", t["id"])
    )
    shown: list[TeamCandidate] = []
    hidden = 0
    for t in teams:
        active = deps.matches.team_has_matches_in_season(t["id"], season["id"], viewer.include_test)
        entries = _marked(index, t, active)
        if active or include_inactive:
            shown.extend(entries)
        elif entries:  # a team this viewer cannot see at all is not "hidden"
            hidden += 1
    return MyTeamResult(status="club", club=club, teams=shown, season=season.get("name"), inactive_hidden=hidden)


def _current_season(deps: ToolDeps) -> dict:
    season = deps.seasons.get_current_season()
    if not season:
        raise _NoCurrentSeason
    return season


def _marked(index: TeamIndex, team: dict, active: bool) -> list[TeamCandidate]:
    return [c.model_copy(update={"active": active}) for c in index.candidates(team)]


def _club_ref(index: TeamIndex, club_id: int | None) -> ClubRef | None:
    club = index.visible_club(club_id)
    return ClubRef(id=club["id"], name=club["name"]) if club else None
