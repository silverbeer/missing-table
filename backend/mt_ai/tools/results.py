"""get_recent_results — a team's last played matches, scored from its side (SB-1526).

"How did we do last weekend?", "our last five games", "how have we done against
Boston?". The other half of get_upcoming_matches, with the same "today": the club's
calendar day, so a game finished at 9pm in Boston is in the results, not tomorrow's.

Played means completed or forfeit with both scores recorded. A result is from the
regulation score, as in the standings: a level match decided on penalties is a draw,
with the shootout alongside. Newest first. `opponent_id` narrows to head-to-head,
across seasons.
"""

from datetime import UTC, date, datetime

import structlog

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.matches import _club, _newest, _provenance
from mt_ai.tools.schemas import (
    ErrorKind,
    RecentResult,
    RecentResultsResult,
    ResultsSummary,
    TeamRef,
    ToolError,
    ToolMeta,
    Viewer,
)
from mt_ai.tools.visibility import DataUnavailableError, load_team_index

logger = structlog.get_logger()

PLAYED_STATUSES = frozenset({"completed", "forfeit"})
MAX_LIMIT = 20


def get_recent_results(
    deps: ToolDeps,
    team_id: int,
    viewer: Viewer,
    age_group_id: int | None = None,
    limit: int = 5,
    opponent_id: int | None = None,
    now: datetime | None = None,
) -> RecentResultsResult:
    def fail(kind: ErrorKind, message: str) -> RecentResultsResult:
        return RecentResultsResult(
            team_id=team_id,
            age_group_id=age_group_id,
            opponent_id=opponent_id,
            error=ToolError(kind=kind, message=message),
        )

    if not 1 <= limit <= MAX_LIMIT:
        return fail("invalid_args", f"limit must be between 1 and {MAX_LIMIT}.")
    if opponent_id == team_id:
        return fail("invalid_args", "opponent_id must be a different team.")

    try:
        index = load_team_index(deps, viewer)
        team = index.teams.get(team_id)
        if team is None:
            return fail("not_found", f"No team with id {team_id}.")
        if opponent_id is not None and opponent_id not in index.teams:
            return fail("not_found", f"No team with id {opponent_id}.")

        tz = index.timezone(team)
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        today = current.astimezone(tz).date()

        rows = deps.matches.get_all_matches(
            team_id=team_id,
            age_group_id=age_group_id,
            end_date=today.isoformat(),
            include_test=viewer.include_test,
            raise_on_error=True,
        )
    except DataUnavailableError as exc:
        return fail("unavailable", f"Match data is unavailable right now ({exc}).")
    except Exception:
        logger.exception("get_recent_results failed", team_id=team_id)
        return fail("unavailable", "Match data is unavailable right now.")

    played = []
    for row in rows:
        if opponent_id is not None and opponent_id not in (row.get("home_team_id"), row.get("away_team_id")):
            continue
        result = _to_result(row, team_id)
        if result and result.match_date <= today:
            played.append((result, row))
    played.sort(key=lambda r: (r[0].match_date, r[0].match_id), reverse=True)

    kept = played[:limit]
    results = [r for r, _ in kept]
    return RecentResultsResult(
        team_id=team_id,
        age_group_id=age_group_id,
        opponent_id=opponent_id,
        today=today,
        timezone=tz.key,
        matches=results,
        summary=_summary(results),
        meta=ToolMeta(
            source=_provenance([r for _, r in kept]),
            as_of=_newest([r for _, r in kept]),
            truncated=len(played) > limit,
        ),
    )


def _to_result(row: dict, team_id: int) -> RecentResult | None:
    """A played match from `team_id`'s side; None when not played or malformed."""
    if row.get("match_status") not in PLAYED_STATUSES:
        return None
    home_score, away_score = row.get("home_score"), row.get("away_score")
    if home_score is None or away_score is None:
        return None  # played but unscored: unknown, not 0-0
    try:
        home_id, away_id = row["home_team_id"], row["away_team_id"]
        is_home = home_id == team_id
        scored, conceded = (home_score, away_score) if is_home else (away_score, home_score)
        return RecentResult(
            match_id=row["id"],
            match_date=date.fromisoformat(str(row["match_date"])[:10]),
            status=row["match_status"],
            home_team=TeamRef(
                id=home_id, name=row.get("home_team_name") or "", club_name=_club(row.get("home_team_club"))
            ),
            away_team=TeamRef(
                id=away_id, name=row.get("away_team_name") or "", club_name=_club(row.get("away_team_club"))
            ),
            is_home=is_home,
            home_score=home_score,
            away_score=away_score,
            home_penalty_score=row.get("home_penalty_score"),
            away_penalty_score=row.get("away_penalty_score"),
            result="W" if scored > conceded else "L" if scored < conceded else "D",
            goals_for=scored,
            goals_against=conceded,
            age_group=row.get("age_group_name"),
            division=row.get("division_name"),
            competition=row.get("match_type_name"),
            league=row.get("league_name"),
            season=row.get("season_name"),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("Skipping malformed match row", match_id=row.get("id"))
        return None


def _summary(results: list[RecentResult]) -> ResultsSummary:
    return ResultsSummary(
        played=len(results),
        wins=sum(r.result == "W" for r in results),
        draws=sum(r.result == "D" for r in results),
        losses=sum(r.result == "L" for r in results),
        goals_for=sum(r.goals_for for r in results),
        goals_against=sum(r.goals_against for r in results),
    )
