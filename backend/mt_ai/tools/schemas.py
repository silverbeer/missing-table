"""Typed inputs and results shared by the MT AI tools.

Two rules from docs/03-architecture/mt2/ai.md shape these models:

- Errors are results, not exceptions. Every result carries an optional
  `ToolError` the agent can explain in plain language.
- Absent is not empty. A list field that is `None` means "not known / not
  tracked"; `[]` means "checked, and there are none".
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ErrorKind = Literal["not_found", "ambiguous", "invalid_args", "unavailable"]
Provenance = Literal["scraper", "user", "mixed"]


class Viewer(BaseModel):
    """Who a tool is answering for. Tools never see more than this viewer could."""

    include_test: bool = False

    @classmethod
    def from_user(cls, user: dict[str, Any] | None) -> "Viewer":
        # Imported here: auth pulls in FastAPI and JWT setup the tools don't need.
        from auth import viewer_sees_test_content

        return cls(include_test=viewer_sees_test_content(user))


class ToolError(BaseModel):
    kind: ErrorKind
    message: str


class ToolMeta(BaseModel):
    """Where a result came from and how much of it there is."""

    source: Provenance | None = None
    as_of: datetime | None = None
    coverage: str | None = None
    truncated: bool = False


class AgeGroupRef(BaseModel):
    id: int
    name: str


class Registration(BaseModel):
    """One competition a team plays in at an age group (a team_mappings row)."""

    league: str | None = None
    division: str | None = None


class TeamCandidate(BaseModel):
    """One team, optionally pinned to one of the age groups it plays in.

    A team can play in several competitions at one age group — League and Flex,
    say. Those are `registrations` of this one candidate, never separate
    candidates: two competitions are not two teams (SB-1146).
    """

    team_id: int
    name: str
    club_name: str | None = None
    league_name: str | None = None
    age_group: AgeGroupRef | None = None
    registrations: list[Registration] = Field(default_factory=list)


class ResolveResult(BaseModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    team: TeamCandidate | None = None
    candidates: list[TeamCandidate] = Field(default_factory=list)
    error: ToolError | None = None
    meta: ToolMeta = Field(default_factory=ToolMeta)


class TeamRef(BaseModel):
    id: int
    name: str
    club_name: str | None = None


class UpcomingMatch(BaseModel):
    match_id: int
    match_date: date
    kickoff: datetime | None = None  # in the club's timezone; None when unscheduled
    status: str
    home_team: TeamRef
    away_team: TeamRef
    is_home: bool
    age_group: str | None = None
    division: str | None = None
    competition: str | None = None
    league: str | None = None


class UpcomingMatchesResult(BaseModel):
    team_id: int
    age_group_id: int | None = None
    today: date | None = None
    timezone: str | None = None
    # None = could not check; [] = checked, nothing scheduled.
    matches: list[UpcomingMatch] | None = None
    error: ToolError | None = None
    meta: ToolMeta = Field(default_factory=ToolMeta)
