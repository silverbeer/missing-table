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
    # Has a match in the current season (SB-1322). None = not checked: only
    # get_my_team checks it.
    active: bool | None = None


class ResolveResult(BaseModel):
    status: Literal["resolved", "ambiguous", "not_found"]
    team: TeamCandidate | None = None
    candidates: list[TeamCandidate] = Field(default_factory=list)
    # not_found only: the team exists, just not at the age asked for. Every age
    # group it does play in, even past the candidate limit (SB-1155).
    other_ages: list[str] = Field(default_factory=list)
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


class RecentResult(BaseModel):
    """One played match, scored from the requested team's side."""

    match_id: int
    match_date: date
    status: str  # "completed" or "forfeit"
    home_team: TeamRef
    away_team: TeamRef
    is_home: bool
    home_score: int
    away_score: int
    # A level match decided on penalties (Flex): the shootout, else None. Still a draw:
    # "result" is the result after regulation, as in the standings.
    home_penalty_score: int | None = None
    away_penalty_score: int | None = None
    result: Literal["W", "D", "L"]
    goals_for: int
    goals_against: int
    age_group: str | None = None
    division: str | None = None
    competition: str | None = None
    league: str | None = None
    season: str | None = None


class ResultsSummary(BaseModel):
    """Totals over the matches returned (not the whole season: see meta.truncated)."""

    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int


class RecentResultsResult(BaseModel):
    team_id: int
    age_group_id: int | None = None
    opponent_id: int | None = None  # set: head-to-head against this team only
    today: date | None = None
    timezone: str | None = None
    # None = could not check (see "error"); [] = no played match found.
    matches: list[RecentResult] | None = None
    summary: ResultsSummary | None = None
    error: ToolError | None = None
    meta: ToolMeta = Field(default_factory=ToolMeta)


class SeasonRef(BaseModel):
    id: int
    name: str


class DivisionRef(BaseModel):
    """A division (conference or Flex bracket) and the league it belongs to."""

    id: int
    name: str
    league: str | None = None


class StandingsOption(BaseModel):
    """One table a team plays in: pass its ids back to get_standings to pick it."""

    age_group: AgeGroupRef
    division: DivisionRef


class StandingsRow(BaseModel):
    position: int  # 1-based, in table order (points, goal difference, goals for)
    team: TeamRef
    played: int
    wins: int
    draws: int  # level after regulation, shootout or not
    losses: int
    shootout_wins: int  # of the draws, won on penalties — worth 2 where the competition scores shootouts
    shootout_losses: int
    goals_for: int  # regulation only; shootout kicks are not goals
    goals_against: int
    goal_difference: int
    points: int
    form: list[str] = Field(default_factory=list)  # last five results, oldest first ("W", "D", "L")
    position_change: int = 0  # places moved since the previous match day; positive is up
    is_requested_team: bool = False


class StandingsCoverage(BaseModel):
    """What the table is made of, as MatchDAO.get_standings reports it.

    `fixtures` counts every match scheduled for the selection, played or not;
    `matches_counted` only the played ones in the table. So `rows: []` with
    `fixtures > 0` is "none played yet", and `fixtures == 0` is "nothing
    scheduled here". `matches_vs_outside_table` > 0 means a combined view
    (qualifying, all) counts results against teams not in the table: a record,
    not a standing.
    """

    match_type: str | None = None
    competitions: list[str] | None = None  # None = every competition ("all")
    matches_counted: int = 0
    fixtures: int = 0
    counted_by_competition: dict[str, int] = Field(default_factory=dict)
    matches_vs_outside_table: int = 0
    teams_outside_table: int = 0
    shootout_points: list[str] = Field(default_factory=list)  # competitions scoring a shootout 2/1


class StandingsResult(BaseModel):
    team_id: int | None = None
    competition: str
    season: SeasonRef | None = None
    age_group: AgeGroupRef | None = None
    division: DivisionRef | None = None
    # None = could not build the table (see "error"); [] = no match played yet
    # (read coverage.fixtures to tell "none played" from "nothing scheduled").
    rows: list[StandingsRow] | None = None
    coverage: StandingsCoverage | None = None
    # ambiguous: every table the team plays in. not_found with a team: the
    # tables it does play in, when none matched the ids given.
    options: list[StandingsOption] = Field(default_factory=list)
    error: ToolError | None = None
    meta: ToolMeta = Field(default_factory=ToolMeta)


class DivisionAgeGroup(BaseModel):
    """One age group a division runs, as far as MT's registrations show."""

    id: int
    name: str
    teams: int  # visible teams registered in the division at this age


class DivisionSummary(BaseModel):
    """A division and its age groups: division.id and an age_groups[].id pick a table."""

    division: DivisionRef
    age_groups: list[DivisionAgeGroup] = Field(default_factory=list)


class DivisionsResult(BaseModel):
    age_group: str | None = None
    league: str | None = None
    query: str | None = None
    # None = could not check (see "error"). Never [] — no match is not_found.
    divisions: list[DivisionSummary] | None = None
    # not_found only: what does exist with fewer filters, so the agent can recover.
    alternatives: list[DivisionSummary] = Field(default_factory=list)
    error: ToolError | None = None
    meta: ToolMeta = Field(default_factory=ToolMeta)
