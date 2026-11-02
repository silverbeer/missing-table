"""get_standings — one table, with the coverage that says how to read it (SB-1496).

The table is `MatchDAO.get_standings`, the same computation (and cache) as
`/api/table`, so MT AI and the Table tab cannot disagree. This module only
decides *which* table, and that is the hard part: a standings table is one
age group in one division, and a team can sit in several.

Which table, given a team:

- Its registrations (`team_mappings`) the viewer may see, narrowed by
  `age_group_id` and `division_id` when given. Exactly one → that one.
- Several, for `League`, `qualifying` or `all` → the team's **home** division:
  the one in a top-level league (`leagues.parent_league_id` null). A Flex
  bracket sits in Flex, a child of Homegrown (SB-1039), so a team in League
  and Flex at one age has exactly one home division. The combined qualifying
  table is keyed by that home division — its teams, their League and Flex
  results (docs/03-architecture/standings.md).
- Anything else — several home divisions (several ages, no age given), or a
  named competition other than League with several registrations — is
  `ambiguous`, with every option listed. The tool does not guess; the agent
  picks an option or asks, and calls again with its ids.

Given a division instead, `age_group_id` is required: divisions span ages, and
a table across ages would merge one team row's U15 and U16 results.

The season defaults as `/api/table` does: the current season, else the most
recent one. No qualification cutoff is reported — MT holds no "top N
qualify" data, and the tool does not invent one.
"""

from dataclasses import dataclass

import structlog

from dao.match_dao import STANDINGS_ALL, STANDINGS_QUALIFYING
from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import (
    AgeGroupRef,
    DivisionRef,
    ErrorKind,
    SeasonRef,
    StandingsCoverage,
    StandingsOption,
    StandingsResult,
    StandingsRow,
    TeamRef,
    ToolError,
    ToolMeta,
    Viewer,
)
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index

logger = structlog.get_logger()

LEAGUE = "League"
COMBINED = frozenset({STANDINGS_QUALIFYING, STANDINGS_ALL})


class _NotFoundError(Exception):
    """An id the viewer cannot see, or that does not exist. The message is for the agent."""


@dataclass(frozen=True)
class Table:
    age_group: AgeGroupRef
    division: DivisionRef
    home: bool  # the division is in a top-level league (not a Flex bracket)

    def option(self) -> StandingsOption:
        return StandingsOption(age_group=self.age_group, division=self.division)


def get_standings(
    deps: ToolDeps,
    viewer: Viewer,
    team_id: int | None = None,
    age_group_id: int | None = None,
    division_id: int | None = None,
    competition: str = LEAGUE,
    season_id: int | None = None,
) -> StandingsResult:
    competition = _competition(competition)

    def result(**fields) -> StandingsResult:
        return StandingsResult(team_id=team_id, competition=competition, **fields)

    def fail(kind: ErrorKind, message: str, **fields) -> StandingsResult:
        return result(error=ToolError(kind=kind, message=message), **fields)

    if not competition:
        return fail("invalid_args", "competition must be a competition name, 'qualifying' or 'all'.")
    if team_id is None and division_id is None:
        return fail("invalid_args", "Give a team_id, or a division_id with its age_group_id.")
    if team_id is None and age_group_id is None:
        return fail("invalid_args", "A division_id needs an age_group_id: divisions span age groups.")

    try:
        index = load_team_index(deps, viewer)
        if team_id is not None:
            team = index.teams.get(team_id)
            if team is None:
                return fail("not_found", f"No team with id {team_id}.")
            every = tables_of(index, team)
            tables = [
                t
                for t in every
                if (age_group_id is None or t.age_group.id == age_group_id)
                and (division_id is None or t.division.id == division_id)
            ]
            if not tables:
                return fail(
                    "not_found",
                    f"{team['name']} plays in no table matching those ids; options lists the ones it does.",
                    options=[t.option() for t in every],
                )
            table = _pick(tables, competition)
            if table is None:
                return fail(
                    "ambiguous",
                    f"{team['name']} plays in {len(tables)} tables; pick one from options.",
                    options=[t.option() for t in tables],
                )
        else:
            table = _division_table(index, division_id, age_group_id)

        season = _season(deps, season_id)
        data = deps.matches.get_standings(
            season_id=season.id,
            age_group_id=table.age_group.id,
            division_id=table.division.id,
            match_type=competition,
            include_test=viewer.include_test,
            raise_on_error=True,
        )
        rows = _rows(data["standings"], index, team_id)
        coverage = StandingsCoverage.model_validate(data["coverage"])
    except _NotFoundError as exc:
        return fail("not_found", str(exc))
    except DataUnavailableError as exc:
        return fail("unavailable", f"Standings are unavailable right now ({exc}).")
    except Exception:
        logger.exception("get_standings failed", team_id=team_id, division_id=division_id)
        return fail("unavailable", "Standings are unavailable right now.")

    return result(
        season=season,
        age_group=table.age_group,
        division=table.division,
        rows=rows,
        coverage=coverage,
        meta=ToolMeta(coverage=_caption(coverage)),
    )


def _competition(value: str | None) -> str:
    """'qualifying' and 'all' in any case; a competition name as given."""
    value = (value or "").strip()
    return value.casefold() if value.casefold() in COMBINED else value


def tables_of(index: TeamIndex, team: dict) -> list[Table]:
    """Every (age group, division) the team is registered in that this viewer may see."""
    out: list[Table] = []
    for mapping in team.get("team_mappings") or []:
        age, division = mapping.get("age_groups"), mapping.get("divisions")
        if not age or not division or division.get("id") is None:
            continue
        league_id = division.get("league_id")
        if not index.include_test and league_id in index.test_league_ids:
            continue
        league = index.leagues.get(league_id or 0) or {}
        table = Table(
            age_group=AgeGroupRef(id=age["id"], name=age["name"]),
            division=DivisionRef(
                id=division["id"],
                name=division["name"],
                league=league.get("name") or (division.get("leagues") or {}).get("name"),
            ),
            home=league.get("parent_league_id") is None,
        )
        if table not in out:
            out.append(table)
    return sorted(out, key=lambda t: (age_number(t.age_group.name), not t.home, t.division.name))


def _pick(tables: list[Table], competition: str) -> Table | None:
    if len(tables) == 1:
        return tables[0]
    if competition == LEAGUE or competition in COMBINED:
        home = [t for t in tables if t.home]
        if len(home) == 1:
            return home[0]
    return None


def _division_table(index: TeamIndex, division_id: int, age_group_id: int) -> Table:
    """The division at that age, if any team the viewer can see is registered there."""
    for team in index.teams.values():
        for table in tables_of(index, team):
            if table.division.id == division_id and table.age_group.id == age_group_id:
                return table
    raise _NotFoundError(f"No division with id {division_id} at age group id {age_group_id}.")


def _season(deps: ToolDeps, season_id: int | None) -> SeasonRef:
    if season_id is None:
        current = deps.seasons.get_current_season()
        if current:
            return SeasonRef(id=current["id"], name=current["name"])
    # get_all_seasons swallows errors and returns []. MT always has seasons, so
    # empty means the read failed. It is newest first, as /api/table relies on.
    seasons = deps.seasons.get_all_seasons()
    if not seasons:
        raise DataUnavailableError("season list unavailable")
    if season_id is None:
        return SeasonRef(id=seasons[0]["id"], name=seasons[0]["name"])
    season = next((s for s in seasons if s.get("id") == season_id), None)
    if season is None:
        raise _NotFoundError(f"No season with id {season_id}.")
    return SeasonRef(id=season["id"], name=season["name"])


def _rows(standings: list[dict], index: TeamIndex, team_id: int | None) -> list[StandingsRow]:
    rows = []
    for position, row in enumerate(standings, start=1):
        if row.get("team_id") is None:
            # Positions still count it: dropping a row must not move the others.
            logger.warning("Skipping standings row without a team id", team=row.get("team"))
            continue
        club = index.visible_club(row.get("club_id"))
        rows.append(
            StandingsRow(
                position=position,
                team=TeamRef(id=row["team_id"], name=row.get("team") or "", club_name=(club or {}).get("name")),
                played=row["played"],
                wins=row["wins"],
                draws=row["draws"],
                losses=row["losses"],
                shootout_wins=row.get("shootout_wins", 0),
                shootout_losses=row.get("shootout_losses", 0),
                goals_for=row["goals_for"],
                goals_against=row["goals_against"],
                goal_difference=row["goal_difference"],
                points=row["points"],
                form=row.get("form") or [],
                position_change=row.get("position_change") or 0,
                is_requested_team=team_id is not None and row["team_id"] == team_id,
            )
        )
    return rows


def _caption(coverage: StandingsCoverage) -> str:
    """The table's denominator in one line (root CLAUDE.md: aggregates state it)."""
    text = f"{coverage.matches_counted} played of {coverage.fixtures} scheduled"
    if coverage.matches_vs_outside_table:
        text += f"; {coverage.matches_vs_outside_table} against {coverage.teams_outside_table} teams outside this table"
    return text


def age_number(name: str) -> int:
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else 999
