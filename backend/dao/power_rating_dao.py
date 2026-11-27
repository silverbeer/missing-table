"""MT Power Rating: the engine's input, and what a run stores (SB-1807).

The engine (`mt_tools.power_rating`) is pure. This module is the two ends of it:

- **Gathering.** One season, age group and league (Homegrown with its Flex child
  league): the League and Flex results, read the way the leaderboards read them
  (`MatchDAO.get_season_results`), plus every tournament match at the age group
  (`tournament_id` set; they carry no division). `to_rated_matches` turns the
  rows into `RatedMatch`es and is pure, so the mapping is testable without a
  database.
- **Storing.** `write_run` writes a run, its ratings and its deltas. Only the
  latest run of a (season, age group, league) keeps deltas: older runs' are
  deleted once the new run is in.
- **Serving** (SB-1808). `run_payload` is a run with its ratings and conference
  names, cached in Redis by run id: a written run never changes, and the worker
  that writes runs cannot clear the API's cache (`caching.md`), so the key is the
  run id and `latest_run` stays uncached. The team reads (`runs`,
  `team_ratings`, `team_deltas`, `matches_by_ids`) are small and uncached.

## Mapping (design "What counts")

| Row | RatedMatch |
|---|---|
| `tournament_id` set | `competition="tournament"`, neutral (no home advantage) |
| League in a division of the league itself | `competition="league"`, `conference` = the division name |
| Flex (the child league) | `competition="flex"` |
| `match_status` forfeit | `forfeit=True`: read, counted in `matches_excluded`, never rated |
| A side that did not field this age group (a play-up) | not passed to the engine; counted as `other_age_group` |
| Completed with no score | not passed; counted as `no_score` |

A team is **in pool** when it has a League fixture of the league itself (a
Homegrown conference) at this age group this season, in any status: a scheduled
fixture is as good a statement of conference membership as a played one, and
early in a season most teams have played few. A match against anyone else, a
Flex-only academy side or a tournament guest, is passed with that side out of
pool, and the engine excludes it as `out_of_pool_opponent`. Late in the season
this is the backtest's production rule (every Homegrown team has played).
Only played matches (`completed`, `forfeit`) are passed to the engine.

## Fingerprint

`fingerprint` hashes the whole engine input with `PARAMS_VERSION`: match ids,
dates, teams, scores, status, competition and pool flags. A score correction, a
forfeit, a new conference registration or a parameter change all change it. A
run whose fingerprint equals the latest run's is not written.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, Any

import structlog

from dao.base_dao import MATCHES_READ_RELATION, BaseDAO, cache_get, cache_set
from dao.side_age_groups import effective_side_age_groups
from mt_tools import power_rating as engine
from mt_tools.power_rating import MasseyResult, PowerRatingResult, RatedMatch

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

logger = structlog.get_logger()

RUNS = "power_rating_runs"
RATINGS = "power_ratings"
DELTAS = "power_rating_match_deltas"

READ_STATUSES = ("completed", "forfeit")
# Every match_status: League fixtures in any of them say which teams are in pool.
POOL_STATUSES = ("scheduled", "completed", "postponed", "cancelled", "tbd", "live", "forfeit")
LEAGUE_COMPETITIONS = {"League": "league", "Flex": "flex"}

# Extra exclusion reasons, beside the engine's (forfeit, out_of_pool_opponent).
OTHER_AGE_GROUP = "other_age_group"
NO_SCORE = "no_score"

# Rows per insert. PostgREST takes larger bodies, but a run is ~6.5k delta rows.
_WRITE_BATCH = 1000
_PAGE = 1000

# The run as served: everything but the fingerprint and parameters.
_RUN_COLUMNS = (
    "id, season_id, age_group_id, league_id, computed_at, through_date, params_version, "
    "matches_counted, matches_excluded, national, publication_reason"
)
_RATING_COLUMNS = (
    "team_id, rating, rank, island, conference_division_id, conference_rank, mp, w, d, l, xconf_mp, sos, tier, badges"
)
_DELTA_COLUMNS = (
    "match_id, team_id, opponent_id, rating_before, opponent_before, expected, result, k, margin_mult, delta"
)
_SCORE_COLUMNS = (
    "id, match_date, home_team_id, away_team_id, home_score, away_score, home_penalty_score, away_penalty_score"
)
# A run's payload never changes once complete; a week is long enough to matter, short enough to expire.
RUN_PAYLOAD_TTL = 7 * 86400

# What the tournament read takes of each match. Explicit, not `*`: no user columns.
_TOURNAMENT_COLUMNS = (
    "id, match_date, scheduled_kickoff, match_status, home_team_id, away_team_id, "
    "home_score, away_score, home_penalty_score, away_penalty_score, "
    "age_group_id, home_age_group_id, away_age_group_id, tournament_id, "
    "match_type:match_types(name)"
)


# --- pure: rows -> engine input ---------------------------------------------------


@dataclass(frozen=True)
class LeagueScope:
    """A top-level league and what its results are read from."""

    league_id: int
    name: str
    league_ids: tuple[int, ...]  # the league and its child leagues (Flex)
    match_type_ids: tuple[int, ...]  # what those leagues declare: League, Flex


@dataclass(frozen=True)
class Gathered:
    """One age group's engine input, and what was read but cannot be rated."""

    matches: tuple[RatedMatch, ...]
    other_age_group: int = 0
    no_score: int = 0
    # Conference (division) name -> division id, for power_ratings.conference_division_id.
    conference_ids: dict[str, int] = field(default_factory=dict)


def _kickoff(value: Any) -> time | None:
    """The time of a scheduled kickoff, in UTC; None when unset or unreadable."""
    if not value:
        return None
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    return moment.time()


def _day(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def to_rated_matches(rows: Iterable[dict], age_group_id: int, home_league_id: int) -> Gathered:
    """League, Flex and tournament rows at one age group -> the engine's input.

    Rows are `get_season_results`' flat shape; tournament rows carry
    `tournament_id` and need no division. A row read twice (by both reads) is
    taken once, as a tournament match. Rows of any status may be passed: only
    `READ_STATUSES` rows are rated, the rest only establish who is in pool.
    """
    by_id: dict[int, dict] = {}
    for row in rows:
        seen = by_id.get(row["id"])
        if seen is None or (row.get("tournament_id") and not seen.get("tournament_id")):
            by_id[row["id"]] = row

    pool: set[int] = set()
    conference_ids: dict[str, int] = {}
    for row in by_id.values():
        if row.get("tournament_id") or row.get("match_type_name") != "League":
            continue
        if row.get("league_id") != home_league_id:
            continue
        home_age, away_age = effective_side_age_groups(row)
        if home_age == age_group_id:
            pool.add(row["home_team_id"])
        if away_age == age_group_id:
            pool.add(row["away_team_id"])
        if row.get("division_name") and row.get("division_id") is not None:
            conference_ids.setdefault(row["division_name"], row["division_id"])

    matches: list[RatedMatch] = []
    other_age_group = no_score = 0
    for row in sorted(by_id.values(), key=lambda r: r["id"]):
        if row.get("match_status") not in READ_STATUSES:
            continue
        if row.get("tournament_id"):
            competition, conference = "tournament", None
        else:
            competition = LEAGUE_COMPETITIONS.get(row.get("match_type_name"))
            if competition is None:
                continue
            league_match = competition == "league" and row.get("league_id") == home_league_id
            conference = row.get("division_name") if league_match else None
        if effective_side_age_groups(row) != (age_group_id, age_group_id):
            other_age_group += 1
            continue
        forfeit = row.get("match_status") == "forfeit"
        hs, as_ = row.get("home_score"), row.get("away_score")
        if not forfeit and (hs is None or as_ is None):
            no_score += 1
            continue
        matches.append(
            RatedMatch(
                match_id=row["id"],
                match_date=_day(row["match_date"]),
                home_team_id=row["home_team_id"],
                away_team_id=row["away_team_id"],
                # A forfeit is never rated, so a missing score there is immaterial.
                home_score=hs or 0,
                away_score=as_ or 0,
                competition=competition,
                neutral=competition == "tournament",
                forfeit=forfeit,
                home_in_pool=row["home_team_id"] in pool,
                away_in_pool=row["away_team_id"] in pool,
                kickoff_time=_kickoff(row.get("scheduled_kickoff")),
                conference=conference,
                home_penalty_score=row.get("home_penalty_score"),
                away_penalty_score=row.get("away_penalty_score"),
            )
        )
    return Gathered(tuple(matches), other_age_group, no_score, conference_ids)


def fingerprint(gathered: Gathered, params_version: str = engine.PARAMS_VERSION) -> str:
    """sha256 of the engine input: equal input, equal fingerprint, whatever the read order."""
    payload = {
        "params_version": params_version,
        "matches": [asdict(m) for m in sorted(gathered.matches, key=lambda m: m.match_id)],
        "other_age_group": gathered.other_age_group,
        "no_score": gathered.no_score,
        "conference_ids": sorted(gathered.conference_ids.items()),
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# --- pure: engine output -> rows ----------------------------------------------------


def engine_params() -> dict[str, Any]:
    """The parameters a run was computed with, stored on the run."""
    return {
        "start_rating": engine.START_RATING,
        "scale": engine.SCALE,
        "k": engine.K,
        "provisional_matches": engine.PROVISIONAL_MATCHES,
        "provisional_k_mult": engine.PROVISIONAL_K_MULT,
        "home_advantage": engine.HOME_ADVANTAGE,
        "margin_cap": engine.MARGIN_CAP,
        "min_matches": engine.MIN_MATCHES,
        "low_cross_conference": engine.LOW_CROSS_CONFERENCE,
        "national_island_share": engine.NATIONAL_ISLAND_SHARE,
        "national_min_cross_conference": engine.NATIONAL_MIN_CROSS_CONFERENCE,
        "massey_cap": engine.MASSEY_CAP,
        "massey_ridge": engine.MASSEY_RIDGE,
    }


def matches_excluded(result: PowerRatingResult, gathered: Gathered) -> dict[str, int]:
    """Every reason a read match was not rated; each key present, 0 when none."""
    return {**result.matches_excluded, OTHER_AGE_GROUP: gathered.other_age_group, NO_SCORE: gathered.no_score}


def run_row(
    *,
    season_id: int,
    age_group_id: int,
    league_id: int,
    result: PowerRatingResult,
    gathered: Gathered,
    input_fingerprint: str,
    computed_at: datetime,
) -> dict[str, Any]:
    rated_ids = {d.match_id for d in result.deltas}
    rated_days = [m.match_date for m in gathered.matches if m.match_id in rated_ids]
    return {
        "season_id": season_id,
        "age_group_id": age_group_id,
        "league_id": league_id,
        "computed_at": computed_at.isoformat(),
        "through_date": max(rated_days).isoformat() if rated_days else None,
        "params": engine_params(),
        "params_version": engine.PARAMS_VERSION,
        "input_fingerprint": input_fingerprint,
        "matches_counted": result.matches_counted,
        "matches_excluded": matches_excluded(result, gathered),
        "national": result.publication.national,
        "publication_reason": result.publication.reason,
    }


def rating_rows(
    result: PowerRatingResult, audit: MasseyResult | None, conference_ids: Mapping[str, int]
) -> list[dict[str, Any]]:
    """One row per rated team, with its national, conference and Massey ranks.

    - `rank`: national lists only, ranked teams in the main island, by rating.
    - `conference_rank`: ranked teams with a conference, within it, by rating.
    - `massey_rank`: ranked teams within their island, by the Massey audit.

    Unranked teams (under MIN_MATCHES) carry no rank of any kind: listed, never placed.
    """
    pub = result.publication
    ranked = [t for t in result.teams if t.ranked]  # result.teams is rating high to low

    national: dict[int, int] = {}
    if pub.national:
        main = [t for t in ranked if t.island == pub.main_island]
        national = {t.team_id: i for i, t in enumerate(main, start=1)}

    per_conference: dict[str, list[int]] = defaultdict(list)
    for t in ranked:
        if t.conference:
            per_conference[t.conference].append(t.team_id)
    conference_rank = {team_id: i for ids in per_conference.values() for i, team_id in enumerate(ids, start=1)}

    massey_rank: dict[int, int] = {}
    if audit is not None:
        per_island: dict[int, list[int]] = defaultdict(list)
        for t in ranked:
            if t.team_id in audit.ratings:
                per_island[t.island].append(t.team_id)
        for ids in per_island.values():
            ordered = sorted(ids, key=lambda team_id: (-audit.ratings[team_id], team_id))
            massey_rank.update({team_id: i for i, team_id in enumerate(ordered, start=1)})

    rows = []
    for t in result.teams:
        badges = []
        if t.ranked and t.provisional:
            badges.append("provisional")
        if t.low_cross_conference:
            badges.append("low_cross_conference")
        rows.append(
            {
                "team_id": t.team_id,
                "rating": t.rating,
                "start_rating": t.start_rating,
                "rank": national.get(t.team_id),
                "island": t.island,
                "conference_division_id": conference_ids.get(t.conference) if t.conference else None,
                "conference_rank": conference_rank.get(t.team_id),
                "mp": t.mp,
                "w": t.w,
                "d": t.d,
                "l": t.l,
                "xconf_mp": t.xconf_mp,
                "sos": t.sos,
                "tier": t.tier,
                "badges": badges,
                "massey_rank": massey_rank.get(t.team_id),
            }
        )
    return rows


def delta_rows(result: PowerRatingResult) -> list[dict[str, Any]]:
    return [
        {
            "match_id": d.match_id,
            "team_id": d.team_id,
            "opponent_id": d.opponent_id,
            "rating_before": d.rating_before,
            "opponent_before": d.opponent_before,
            "expected": d.expected,
            "result": d.result,
            "k": d.k,
            "margin_mult": d.margin_mult,
            "delta": d.delta,
        }
        for d in result.deltas
    ]


def _batches(rows: list[dict], size: int = _WRITE_BATCH) -> Iterable[list[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


# --- the DAO ------------------------------------------------------------------------


class PowerRatingDAO(BaseDAO):
    """Read the Power Rating's input; read and write its runs."""

    def __init__(self, connection_holder):
        super().__init__(connection_holder)
        self._match_dao = None

    @property
    def match_dao(self):
        """MatchDAO over the same connection; imported here because match_dao imports base_dao."""
        if self._match_dao is None:
            from dao.match_dao import MatchDAO

            self._match_dao = MatchDAO(self.connection_holder)
        return self._match_dao

    # --- reference data -----------------------------------------------------------

    def current_season_id(self) -> int | None:
        from dao.season_dao import SeasonDAO

        return SeasonDAO(self.connection_holder).get_current_season_id()

    def resolve_league(self, name: str) -> LeagueScope | None:
        """A top-level, non-test league by name (case-insensitive), with its child leagues."""
        rows = self.client.table("leagues").select("id, name, parent_league_id, match_type_id, is_test").execute().data
        rows = [r for r in rows or [] if not r.get("is_test")]
        league = next(
            (
                r
                for r in rows
                if r.get("parent_league_id") is None and str(r.get("name", "")).casefold() == name.strip().casefold()
            ),
            None,
        )
        if league is None:
            return None
        covered = [league, *(r for r in rows if r.get("parent_league_id") == league["id"])]
        return LeagueScope(
            league_id=league["id"],
            name=league["name"],
            league_ids=tuple(r["id"] for r in covered),
            match_type_ids=tuple(sorted({r["match_type_id"] for r in covered if r.get("match_type_id") is not None})),
        )

    def age_group_ids(self, names: Iterable[str]) -> dict[str, int]:
        """Name -> id for the age groups that exist; unknown names are absent."""
        wanted = list(names)
        rows = self.client.table("age_groups").select("id, name").in_("name", wanted).execute().data
        return {r["name"]: r["id"] for r in rows or []}

    # --- input --------------------------------------------------------------------

    def get_tournament_results(self, season_id: int, age_group_id: int) -> list[dict]:
        """Played tournament matches at one age group (or with a side at it), non-test, paged."""
        a = int(age_group_id)
        rows: list[dict] = []
        while True:
            page = (
                self.client.table(MATCHES_READ_RELATION)
                .select(_TOURNAMENT_COLUMNS)
                .eq("season_id", season_id)
                .or_(f"age_group_id.eq.{a},home_age_group_id.eq.{a},away_age_group_id.eq.{a}")
                .not_.is_("tournament_id", "null")
                .in_("match_status", list(READ_STATUSES))
                .eq("is_test", False)
                .order("match_date")
                .order("id")
                .range(len(rows), len(rows) + _PAGE - 1)
                .execute()
            ).data or []
            if not page:
                break
            rows.extend(page)
        return [
            {**r, "match_type_name": (r.get("match_type") or {}).get("name"), "league_id": None, "division_name": None}
            for r in rows
        ]

    def gather(self, season_id: int, age_group_id: int, scope: LeagueScope) -> Gathered:
        """One age group's engine input. Raises on a read error: "could not read" is not "no matches"."""
        league_rows = self.match_dao.get_season_results(
            season_id=season_id,
            age_group_id=age_group_id,
            league_ids=scope.league_ids,
            match_type_ids=scope.match_type_ids,
            statuses=POOL_STATUSES,
            include_test=False,
        )
        tournament_rows = self.get_tournament_results(season_id, age_group_id)
        return to_rated_matches([*league_rows, *tournament_rows], age_group_id, scope.league_id)

    # --- runs ---------------------------------------------------------------------

    def _runs(self, season_id: int, age_group_id: int, league_id: int):
        return (
            self.client.table(RUNS)
            .select("id, computed_at, input_fingerprint")
            .eq("season_id", season_id)
            .eq("age_group_id", age_group_id)
            .eq("league_id", league_id)
        )

    def latest_run(self, season_id: int, age_group_id: int, league_id: int) -> dict | None:
        """The newest run (id, computed_at, input_fingerprint), or None. Uncached by design."""
        rows = (
            self._runs(season_id, age_group_id, league_id)
            .order("computed_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        ).data
        return rows[0] if rows else None

    def latest_run_id(self, season_id: int, age_group_id: int, league_id: int) -> int | None:
        run = self.latest_run(season_id, age_group_id, league_id)
        return run["id"] if run else None

    def run_as_of(self, season_id: int, age_group_id: int, league_id: int, at: datetime) -> dict | None:
        """The run users saw at `at`: the newest computed at or before it. For 7-day movement."""
        rows = (
            self._runs(season_id, age_group_id, league_id)
            .lte("computed_at", at.isoformat())
            .order("computed_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        ).data
        return rows[0] if rows else None

    def write_run(self, run: dict, ratings: list[dict], deltas: list[dict]) -> int:
        """Insert a run with its ratings and deltas; drop older runs' deltas. Returns the run id.

        PostgREST has no multi-statement transaction, so a failure after the run
        row is in deletes it again (ratings and deltas cascade) and re-raises:
        a half-written run must never be the latest.
        """
        run_id = self.client.table(RUNS).insert(run).execute().data[0]["id"]
        try:
            for batch in _batches([{**r, "run_id": run_id} for r in ratings]):
                self.client.table(RATINGS).insert(batch).execute()
            for batch in _batches([{**d, "run_id": run_id} for d in deltas]):
                self.client.table(DELTAS).insert(batch).execute()
        except Exception:
            logger.exception("power_rating_write_failed", run_id=run_id)
            self.client.table(RUNS).delete().eq("id", run_id).execute()
            raise
        same_scope = self._runs(run["season_id"], run["age_group_id"], run["league_id"])
        older = [r["id"] for r in same_scope.neq("id", run_id).execute().data or []]
        if older:
            # Latest run only (design "Data model"). A failure here leaves stale
            # deltas on old runs, which nothing reads; the next write retries it.
            try:
                self.client.table(DELTAS).delete().in_("run_id", older).execute()
            except Exception:
                logger.exception("power_rating_old_deltas_not_deleted", run_id=run_id)
        return run_id

    # --- serving (SB-1808) --------------------------------------------------------

    def run_payload(self, run_id: int) -> dict | None:
        """A run, its ratings and its conferences' names, cached by run id. None for no such run.

        A run is written row first, then ratings, so a reader can catch it with
        none of them (all ratings go in one insert: under `_WRITE_BATCH` teams).
        Such a payload is returned but not cached, so the next read sees it whole.
        """
        key = f"mt:dao:power_rating:run:{int(run_id)}"
        cached = cache_get(key)
        if cached is not None:
            return cached
        rows = self.client.table(RUNS).select(_RUN_COLUMNS).eq("id", run_id).limit(1).execute().data
        if not rows:
            return None
        ratings: list[dict] = []
        while True:
            page = (
                self.client.table(RATINGS)
                .select(_RATING_COLUMNS)
                .eq("run_id", run_id)
                .order("team_id")
                .range(len(ratings), len(ratings) + _PAGE - 1)
                .execute()
            ).data or []
            ratings.extend(page)
            if len(page) < _PAGE:
                break
        division_ids = sorted({r["conference_division_id"] for r in ratings if r.get("conference_division_id")})
        conferences: dict[str, str] = {}
        if division_ids:
            divisions = self.client.table("divisions").select("id, name").in_("id", division_ids).execute().data
            # JSON keys are strings: the cached copy and the fresh one must look alike.
            conferences = {str(d["id"]): d["name"] for d in divisions or []}
        payload = {"run": rows[0], "ratings": ratings, "conferences": conferences}
        if ratings or not rows[0].get("matches_counted"):
            cache_set(key, payload, RUN_PAYLOAD_TTL)
        return payload

    def runs(self, season_id: int, age_group_id: int, league_id: int) -> list[dict]:
        """Every run of a scope, oldest first (id, computed_at, through_date)."""
        return (
            self.client.table(RUNS)
            .select("id, computed_at, through_date")
            .eq("season_id", season_id)
            .eq("age_group_id", age_group_id)
            .eq("league_id", league_id)
            .order("computed_at")
            .order("id")
            .execute()
        ).data or []

    def team_ratings(self, team_id: int, run_ids: Iterable[int]) -> list[dict]:
        """One team's rating rows in the given runs; a run it was not rated in has none."""
        ids = list(run_ids)
        if not ids:
            return []
        return (
            self.client.table(RATINGS)
            .select("run_id, rating, rank, conference_rank, mp")
            .eq("team_id", team_id)
            .in_("run_id", ids)
            .execute()
        ).data or []

    def team_deltas(self, run_id: int, team_id: int) -> list[dict]:
        """One team's per-match rating changes in a run (only the latest run keeps any)."""
        return (
            self.client.table(DELTAS).select(_DELTA_COLUMNS).eq("run_id", run_id).eq("team_id", team_id).execute()
        ).data or []

    def matches_by_ids(self, match_ids: Iterable[int]) -> list[dict]:
        """Date and score of the given matches, for "why it moved"."""
        ids = sorted(set(match_ids))
        if not ids:
            return []
        return self.client.table(MATCHES_READ_RELATION).select(_SCORE_COLUMNS).in_("id", ids).execute().data or []
