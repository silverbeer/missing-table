"""search_teams — turn what a person typed into an MT team (and age group).

Resolution is deliberately conservative, like TeamDAO.resolve_team_by_name:

- `resolved` only for an exact name or alias match that pins one team in one
  age group.
- `ambiguous` when several teams share the name, when a multi-age team was
  named without an age, or when only near-matches exist. The agent asks
  rather than guesses.
- `not_found` when nothing plausible exists — including when the team exists
  but not at the age asked for (the candidates then list the ages it has).
"""

import re

import structlog

from dao.team_dao import TeamDAO
from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import ErrorKind, ResolveResult, TeamCandidate, ToolError, ToolMeta, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index

logger = structlog.get_logger()

_AGE_TOKEN = re.compile(r"\bu-?(\d{1,2})\b", re.IGNORECASE)
# ilike treats these as wildcards; a user-typed name containing one must not
# reach the database as a pattern.
_LIKE_METACHARS = frozenset("%_\\")
_STOPWORDS = TeamDAO._SIMILAR_STOPWORDS
MAX_CANDIDATES = 8


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def split_age_group(query: str) -> tuple[str, str | None]:
    """'Boston United U15' -> ('Boston United', 'U15')."""
    match = _AGE_TOKEN.search(query)
    if not match:
        return " ".join(query.split()), None
    name = _AGE_TOKEN.sub(" ", query, count=1)
    return " ".join(name.split()), f"U{int(match.group(1))}"


def search_teams(
    deps: ToolDeps,
    query: str,
    viewer: Viewer,
    age_group: str | None = None,
    limit: int = MAX_CANDIDATES,
) -> ResolveResult:
    name, age_in_query = split_age_group(query or "")
    age = age_group or age_in_query
    if not name:
        return _error("invalid_args", "A team name is required.")
    if not 1 <= limit <= MAX_CANDIDATES:
        return _error("invalid_args", f"limit must be between 1 and {MAX_CANDIDATES}.")

    try:
        index = load_team_index(deps, viewer)
        exact = _exact_or_alias(deps, index, name)
        if exact:
            return _from_teams(index, exact, age, limit)
        return _near_matches(index, name, age, limit)
    except DataUnavailableError as exc:
        return _error("unavailable", f"Team data is unavailable right now ({exc}).")
    except Exception:
        logger.exception("search_teams failed", query=query)
        return _error("unavailable", "Team data is unavailable right now.")


def _exact_or_alias(deps: ToolDeps, index: TeamIndex, name: str) -> list[dict]:
    wanted = _normalize(name)
    exact = [t for t in index.teams.values() if _normalize(t.get("name", "")) == wanted]
    if exact:
        return sorted(exact, key=lambda t: t["id"])
    if _LIKE_METACHARS & set(name):
        return []
    aliased = deps.teams.resolve_team_by_name(name)
    # A hit on a team this viewer can't see is reported as no hit at all.
    if aliased and aliased.get("id") in index.teams:
        return [index.teams[aliased["id"]]]
    return []


def _from_teams(index: TeamIndex, teams: list[dict], age: str | None, limit: int) -> ResolveResult:
    candidates = [c for team in teams for c in index.candidates(team, age)]
    if not candidates:
        # The team exists, just not at that age: say which ages it has.
        every_age = [c for team in teams for c in index.candidates(team)]
        return ResolveResult(
            status="not_found",
            candidates=every_age[:limit],
            other_ages=_age_names(every_age),
            meta=_meta(every_age, limit),
        )
    if len(candidates) == 1:
        return ResolveResult(status="resolved", team=candidates[0])
    return ResolveResult(status="ambiguous", candidates=candidates[:limit], meta=_meta(candidates, limit))


def _near_matches(index: TeamIndex, name: str, age: str | None, limit: int) -> ResolveResult:
    words = [w for w in _normalize(name).split() if len(w) >= 4 and w not in _STOPWORDS]
    scored: list[tuple[int, str, dict]] = []
    for team in index.teams.values():
        team_name = _normalize(team.get("name", ""))
        score = sum(1 for w in words if w in team_name)
        if score:
            scored.append((score, team_name, team))
    scored.sort(key=lambda s: (-s[0], s[1]))

    candidates = [c for _, _, team in scored for c in index.candidates(team, age)]
    if not candidates:
        return ResolveResult(status="not_found")
    # Near-matches are never resolved, even when there is only one.
    return ResolveResult(status="ambiguous", candidates=candidates[:limit], meta=_meta(candidates, limit))


def _age_names(candidates: list[TeamCandidate]) -> list[str]:
    """Distinct age-group names, in candidate order; age-less candidates add none."""
    names: list[str] = []
    for c in candidates:
        if c.age_group and c.age_group.name not in names:
            names.append(c.age_group.name)
    return names


def _meta(candidates: list[TeamCandidate], limit: int) -> ToolMeta:
    return ToolMeta(truncated=len(candidates) > limit)


def _error(kind: ErrorKind, message: str) -> ResolveResult:
    return ResolveResult(status="not_found", error=ToolError(kind=kind, message=message))
