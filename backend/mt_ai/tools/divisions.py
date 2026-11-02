"""list_divisions — resolve a division by name, for get_standings (SB-1503).

"Who's top of the U15 Northeast table?" names a division, not a team, and
get_standings by division needs its id and an age group id. This tool lists
the divisions a viewer can see, each with the age groups it runs, so the agent
can pass `division.id` and `age_groups[].id` straight to get_standings.

A division is listed when a team the viewer may see is registered in it
(`team_mappings`), through the same team index and the same per-registration
visibility as search_teams and get_standings (`tables_of`). So a test league's
division never reaches a real viewer, and a division nobody plays in is not
listed — it has no table to ask about.

Filters are optional and combine: `age_group` ("U15", "u-15", "15") and
`league` ("Homegrown", "Flex") match a name exactly, case-insensitively;
`query` matches part of a division or league name ("Northeast", "new
england"). No match is `not_found` with `alternatives`: what exists with
fewer filters, so the agent can recover or ask rather than give up.
"""

from collections.abc import Callable
from itertools import combinations

import structlog

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import (
    DivisionAgeGroup,
    DivisionsResult,
    DivisionSummary,
    ErrorKind,
    ToolError,
    ToolMeta,
    Viewer,
)
from mt_ai.tools.standings import Table, age_number, tables_of
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index

logger = structlog.get_logger()

MAX_DIVISIONS = 50
MAX_FILTER_LENGTH = 100
MAX_NAMED = 20  # alternatives spelled out in a not_found message

# Dropped in this order to find alternatives. A named division that does not
# run that age lists the ages it does; a query matching nothing lists what
# exists at that age.
FILTERS = ("age_group", "league", "query")

Registrations = dict[tuple[int, int], tuple[Table, set[int]]]


def list_divisions(
    deps: ToolDeps,
    viewer: Viewer,
    age_group: str | None = None,
    league: str | None = None,
    query: str | None = None,
) -> DivisionsResult:
    # Blank means "no filter": models often send "" for an optional argument, and an
    # error there would cost a round trip for nothing.
    age_group, league, query = (v if v is None or v.strip() else None for v in (age_group, league, query))
    filters = {"query": query, "league": league, "age_group": age_group}

    def fail(kind: ErrorKind, message: str, **fields) -> DivisionsResult:
        return DivisionsResult(
            age_group=age_group, league=league, query=query, error=ToolError(kind=kind, message=message), **fields
        )

    for name, value in filters.items():
        if value is not None and len(value) > MAX_FILTER_LENGTH:
            return fail("invalid_args", f"{name} must be at most {MAX_FILTER_LENGTH} characters.")

    try:
        registrations = _registrations(load_team_index(deps, viewer))
    except DataUnavailableError as exc:
        return fail("unavailable", f"Division data is unavailable right now ({exc}).")
    except Exception:
        logger.exception("list_divisions failed", age_group=age_group, league=league, query=query)
        return fail("unavailable", "Division data is unavailable right now.")

    divisions = _matching(registrations, **filters)
    if not divisions:
        return _not_found(registrations, filters, fail)
    return DivisionsResult(
        age_group=age_group,
        league=league,
        query=query,
        divisions=divisions[:MAX_DIVISIONS],
        meta=ToolMeta(truncated=len(divisions) > MAX_DIVISIONS),
    )


def _registrations(index: TeamIndex) -> Registrations:
    """(division id, age group id) → the table and the visible teams registered there."""
    out: Registrations = {}
    for team in index.teams.values():
        for table in tables_of(index, team):
            _, teams = out.setdefault((table.division.id, table.age_group.id), (table, set()))
            teams.add(team["id"])
    return out


def _matching(
    registrations: Registrations, query: str | None, league: str | None, age_group: str | None
) -> list[DivisionSummary]:
    by_division: dict[int, DivisionSummary] = {}
    for table, teams in registrations.values():
        division = table.division
        if age_group and _age_key(table.age_group.name) != _age_key(age_group):
            continue
        if league and _normalize(division.league or "") != _normalize(league):
            continue
        if query and not _mentions(table, _normalize(query)):
            continue
        summary = by_division.setdefault(division.id, DivisionSummary(division=division))
        summary.age_groups.append(DivisionAgeGroup(id=table.age_group.id, name=table.age_group.name, teams=len(teams)))

    for summary in by_division.values():
        summary.age_groups.sort(key=lambda a: (age_number(a.name), a.name))
    return sorted(
        by_division.values(),
        key=lambda s: (_normalize(s.division.league or ""), _normalize(s.division.name), s.division.id),
    )


def _not_found(
    registrations: Registrations, filters: dict[str, str | None], fail: Callable[..., DivisionsResult]
) -> DivisionsResult:
    """not_found, with what exists once the fewest filters are dropped."""
    given = [name for name in FILTERS if filters[name] is not None]
    wanted = _describe(filters)
    if not given:
        return fail("not_found", "MT has no divisions with registered teams.")

    for size in range(1, len(given) + 1):
        for dropped in combinations(given, size):
            relaxed = {name: None if name in dropped else value for name, value in filters.items()}
            alternatives = _matching(registrations, **relaxed)
            if alternatives:
                names = ", ".join(_label(s) for s in alternatives[:MAX_NAMED])
                more = f" and {len(alternatives) - MAX_NAMED} more" if len(alternatives) > MAX_NAMED else ""
                scope = _describe(relaxed) or "in MT"
                return fail(
                    "not_found",
                    f"No division {wanted}. Divisions {scope}: {names}{more}.",
                    alternatives=alternatives[:MAX_DIVISIONS],
                    meta=ToolMeta(truncated=len(alternatives) > MAX_DIVISIONS),
                )
    return fail("not_found", f"No division {wanted}.")  # unreachable while MT has any division


def _describe(filters: dict[str, str | None]) -> str:
    parts = []
    if filters["query"] is not None:
        parts.append(f"matching '{filters['query'].strip()}'")
    if filters["league"] is not None:
        parts.append(f"in league {filters['league'].strip()}")
    if filters["age_group"] is not None:
        parts.append(f"at {filters['age_group'].strip()}")
    return " ".join(parts)


def _label(summary: DivisionSummary) -> str:
    league = f" ({summary.division.league})" if summary.division.league else ""
    ages = "/".join(a.name for a in summary.age_groups)
    return f"{summary.division.name}{league} {ages}"


def _mentions(table: Table, wanted: str) -> bool:
    name, league = _normalize(table.division.name), _normalize(table.division.league or "")
    return any(wanted in text for text in (name, league, f"{league} {name}", f"{name} {league}"))


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _age_key(name: str) -> str:
    """'U15', 'u15', 'U-15', 'u 15' and '15' are one age group."""
    key = "".join(ch for ch in name.casefold() if ch.isalnum())
    return f"u{key}" if key.isdigit() else key
