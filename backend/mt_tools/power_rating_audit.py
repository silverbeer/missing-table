"""The admin Massey audit of the MT Power Rating (SB-1812).

Elo is published; Massey runs beside it every night as a check (design
"Open decisions" 1). This reads the latest stored run and lists the teams whose
two places differ by more than `min_gap` (default 30, about the worst 5% at the
2026-11-26 freeze). Investigate, never auto-fix: nothing here changes a rating.

## Like with like

The stored `massey_rank` counts ranked teams (6+ matches) **within their
island**, because separate islands are not on one scale. The national `rank`
counts the main island only, and only on a national run, so it cannot be the
other side. The Elo rank here is therefore recomputed the same way the Massey
one was stored: the same teams, within the same island, by rating, ties by
team id (`mt_tools.power_rating.rank_gaps` does the same at compute time).

Two layers, as in `power_rating_read`: `build_audit` is pure over the stored
rows, `get_power_rating_audit` gathers them.
"""

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import ToolError
from mt_ai.tools.visibility import DataUnavailableError
from mt_tools.leaderboards import _InvalidArgsError
from mt_tools.power_rating import MIN_MATCHES, RANK_GAP_FLAG, _ranks
from mt_tools.power_rating_read import (
    UNAVAILABLE,
    RunRef,
    TeamInfo,
    _conference_names,
    _payload,
    _scope,
    _team_info,
    no_run,
    run_ref,
)

logger = structlog.get_logger()

SCOPE = (
    "Within each island: ranked teams (6+ matches) ordered by Elo rating and by Massey, so both ranks count "
    "the same teams."
)
NOTE = "Investigate, don't auto-fix: a large gap usually means few matches or few cross-conference matches."


class AuditRow(BaseModel):
    team_id: int
    team: str
    conference: str | None = None
    island: int
    elo_rating: int
    elo_rank: int  # within the island
    massey_rank: int  # within the island
    gap: int  # massey_rank - elo_rank: positive when Elo ranks the team higher
    mp: int
    xconf_mp: int
    badges: list[str]


class AuditIsland(BaseModel):
    island: int
    teams: int  # ranked teams compared in this island
    flagged: int
    rank_correlation: float | None = None  # Spearman; null under 2 teams


class PowerRatingAuditResult(BaseModel):
    """Elo vs Massey places in the latest run. `teams` [] with `reason` when there is nothing to compare."""

    league: str
    age_group: str | None = None
    season: str | None = None
    run: RunRef | None = None
    min_gap: int = RANK_GAP_FLAG
    scope: str = SCOPE
    note: str = NOTE
    teams_compared: int = 0
    flagged_count: int = 0
    rank_correlation: float | None = None  # of the largest island
    islands: list[AuditIsland] = []
    teams: list[AuditRow] | None = None
    reason: str | None = None
    error: ToolError | None = None


def spearman(a: Mapping[int, int], b: Mapping[int, int]) -> float | None:
    """Rank correlation of two tie-free rankings of the same teams; None under 2 teams."""
    n = len(a)
    if n < 2:
        return None
    d2 = sum((a[t] - b[t]) ** 2 for t in a)
    return round(1 - 6 * d2 / (n * (n * n - 1)), 3)


def build_audit(
    payload: Mapping[str, Any],
    massey_ranks: Mapping[int, int],
    teams: Mapping[int, TeamInfo],
    *,
    league: str,
    age_group: str,
    season: str,
    min_gap: int = RANK_GAP_FLAG,
) -> PowerRatingAuditResult:
    """Teams whose Elo and Massey places, within their island, differ by more than `min_gap`.

    A team missing from `teams` is still compared and listed, by id: it was in
    the run, so it moved the other teams' places.
    """
    conferences = _conference_names(payload)
    by_island: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for r in payload.get("ratings") or []:
        if r["mp"] >= MIN_MATCHES and r["team_id"] in massey_ranks:
            by_island[r["island"]].append(r)

    rows: list[AuditRow] = []
    islands: list[AuditIsland] = []
    for island, members in by_island.items():
        ids = [r["team_id"] for r in members]
        elo = _ranks(ids, {r["team_id"]: r["rating"] for r in members})
        massey = {t: massey_ranks[t] for t in ids}
        flagged = []
        for r in members:
            t = r["team_id"]
            gap = massey[t] - elo[t]
            if abs(gap) <= min_gap:
                continue
            info = teams.get(t)
            flagged.append(
                AuditRow(
                    team_id=t,
                    team=info.name if info else str(t),
                    conference=conferences.get(t),
                    island=island,
                    elo_rating=round(r["rating"]),
                    elo_rank=elo[t],
                    massey_rank=massey[t],
                    gap=gap,
                    mp=r["mp"],
                    xconf_mp=r.get("xconf_mp") or 0,
                    badges=list(r.get("badges") or []),
                )
            )
        rows.extend(flagged)
        islands.append(
            AuditIsland(island=island, teams=len(ids), flagged=len(flagged), rank_correlation=spearman(elo, massey))
        )

    islands.sort(key=lambda i: (-i.teams, i.island))
    rows.sort(key=lambda g: (-abs(g.gap), g.team_id))
    compared = sum(i.teams for i in islands)
    return PowerRatingAuditResult(
        league=league,
        age_group=age_group,
        season=season,
        run=run_ref(payload["run"]),
        min_gap=min_gap,
        teams_compared=compared,
        flagged_count=len(rows),
        rank_correlation=islands[0].rank_correlation if islands else None,
        islands=islands,
        teams=rows,
        reason=None if compared else f"No ranked teams with a Massey rank at {age_group} {league} in {season}.",
    )


def get_power_rating_audit(
    deps: ToolDeps,
    age_group: str,
    league: str = "Homegrown",
    season: str | None = None,
    *,
    min_gap: int = RANK_GAP_FLAG,
    today: date | None = None,
) -> PowerRatingAuditResult:
    """The Elo vs Massey audit of the latest run for `league` at `age_group`."""

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> PowerRatingAuditResult:
        return PowerRatingAuditResult(league=league, min_gap=min_gap, error=ToolError(kind=kind, message=message))

    if min_gap < 0:
        return fail("invalid_args", "min_gap must be 0 or more.")
    store = deps.power_rating
    try:
        if store is None:
            raise DataUnavailableError("no power rating source")
        s = _scope(deps, league, age_group, season, today or date.today())
        latest = store.latest_run(s.season_id, s.age_group_id, s.league_id)
        if latest is None:
            return PowerRatingAuditResult(
                league=s.league,
                age_group=s.age_group,
                season=s.season,
                min_gap=min_gap,
                teams=[],
                reason=no_run(s.league, s.age_group, s.season).reason,
            )
        payload = _payload(store, latest["id"])
        result = build_audit(
            payload,
            store.massey_ranks(latest["id"]),
            _team_info(s.index),
            league=s.league,
            age_group=s.age_group,
            season=s.season,
            min_gap=min_gap,
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("power_rating_audit_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_power_rating_audit failed")
        return fail("unavailable", UNAVAILABLE)
    logger.info(
        "power_rating_audit_served",
        league=result.league,
        age_group=result.age_group,
        run_id=result.run.id if result.run else None,
        compared=result.teams_compared,
        flagged=result.flagged_count,
    )
    return result
