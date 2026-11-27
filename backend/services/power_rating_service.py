"""Recompute the MT Power Rating (SB-1807).

Orchestration only: per age group, gather the season's matches through the DAO,
skip when the input fingerprint matches the latest run, otherwise rate with the
pure engine (`mt_tools.power_rating`) and write the run. The nightly Celery beat
task (`power_rating.recompute_all`) and `POST /api/admin/power-rating/recompute`
both call `recompute`, so the two can never rate differently.

One age group failing does not stop the others: it is reported as `failed` in
the summary, with the detail in the log.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

import structlog
from pydantic import BaseModel

from dao.power_rating_dao import (
    Gathered,
    LeagueScope,
    delta_rows,
    fingerprint,
    matches_excluded,
    rating_rows,
    run_row,
)
from mt_tools.power_rating import massey, rate

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = structlog.get_logger()

DEFAULT_AGE_GROUPS = ("U15", "U16", "U17", "U19")
DEFAULT_LEAGUE = "Homegrown"


class PowerRatingStore(Protocol):
    """What `recompute` needs of the DAO (`dao.power_rating_dao.PowerRatingDAO`)."""

    def current_season_id(self) -> int | None: ...
    def resolve_league(self, name: str) -> LeagueScope | None: ...
    def age_group_ids(self, names: Iterable[str]) -> dict[str, int]: ...
    def gather(self, season_id: int, age_group_id: int, scope: LeagueScope) -> Gathered: ...
    def latest_run(self, season_id: int, age_group_id: int, league_id: int) -> dict | None: ...
    def write_run(self, run: dict, ratings: list[dict], deltas: list[dict]) -> int: ...


class InvalidRecomputeError(ValueError):
    """Unknown league or age group, or no season: the caller's input, not MT's state."""


class AgeGroupSummary(BaseModel):
    age_group: str
    # written: a new run; unchanged: same input as the latest run, nothing written;
    # failed: see the log.
    status: Literal["written", "unchanged", "failed"]
    run_id: int | None = None  # the new run, or the latest one when unchanged
    matches_counted: int | None = None
    matches_excluded: dict[str, int] | None = None
    teams: int | None = None
    national: bool | None = None
    reason: str | None = None


class RecomputeSummary(BaseModel):
    season_id: int
    league: str
    computed_at: datetime
    age_groups: list[AgeGroupSummary]


def recompute(
    store: PowerRatingStore,
    season_id: int | None = None,
    age_groups: Iterable[str] = DEFAULT_AGE_GROUPS,
    league: str = DEFAULT_LEAGUE,
    *,
    now: datetime | None = None,
) -> RecomputeSummary:
    """Rate each age group's season and store every run whose input changed.

    Raises InvalidRecomputeError for an unknown league or age group, or no current season.
    """
    names = list(dict.fromkeys(age_groups))
    computed_at = now or datetime.now(UTC)
    if season_id is None:
        season_id = store.current_season_id()
        if season_id is None:
            raise InvalidRecomputeError("No current season is set.")
    scope = store.resolve_league(league)
    if scope is None:
        raise InvalidRecomputeError(f"No top-level league named {league!r}.")
    ids = store.age_group_ids(names)
    unknown = [n for n in names if n not in ids]
    if unknown:
        raise InvalidRecomputeError(f"Unknown age group(s): {', '.join(unknown)}.")

    summaries = []
    for name in names:
        try:
            summaries.append(_one(store, season_id, ids[name], name, scope, computed_at))
        except Exception:
            logger.exception("power_rating_recompute_failed", season_id=season_id, age_group=name)
            summaries.append(AgeGroupSummary(age_group=name, status="failed", reason="Could not recompute."))
    summary = RecomputeSummary(season_id=season_id, league=scope.name, computed_at=computed_at, age_groups=summaries)
    logger.info(
        "power_rating_recomputed",
        season_id=season_id,
        league=scope.name,
        **{s.age_group: s.status for s in summaries},
    )
    return summary


def _one(
    store: PowerRatingStore,
    season_id: int,
    age_group_id: int,
    name: str,
    scope: LeagueScope,
    computed_at: datetime,
) -> AgeGroupSummary:
    gathered = store.gather(season_id, age_group_id, scope)
    digest = fingerprint(gathered)
    latest = store.latest_run(season_id, age_group_id, scope.league_id)
    if latest and latest.get("input_fingerprint") == digest:
        return AgeGroupSummary(age_group=name, status="unchanged", run_id=latest["id"])

    result = rate(gathered.matches)
    audit = massey(gathered.matches)
    run: dict[str, Any] = run_row(
        season_id=season_id,
        age_group_id=age_group_id,
        league_id=scope.league_id,
        result=result,
        gathered=gathered,
        input_fingerprint=digest,
        computed_at=computed_at,
    )
    run_id = store.write_run(run, rating_rows(result, audit, gathered.conference_ids), delta_rows(result))
    return AgeGroupSummary(
        age_group=name,
        status="written",
        run_id=run_id,
        matches_counted=result.matches_counted,
        matches_excluded=matches_excluded(result, gathered),
        teams=len(result.teams),
        national=result.publication.national,
        reason=result.publication.reason,
    )
