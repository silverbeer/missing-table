"""The MT Power Rating as served: one stored run, read for people (SB-1808).

`GET /api/rankings`, `GET /api/rankings/teams/{id}`, the mt-mcp tools
`get_power_rating` / `get_power_rating_team` and `mt rankings` all call the two
gathering functions here, so the web, the CLI and MT AI can never disagree. The
engine (`mt_tools.power_rating`) computed the numbers and the nightly job stored
them; nothing here rates anything.

Two layers, so the reading is testable without a database:

- **Gathering** (`get_power_rating`, `get_power_rating_team`) resolves the league,
  age group and season the way the leaderboards do, then reads the latest run
  through `ToolDeps.power_rating`.
- **Building** (`build_rankings`, `build_team`, `coverage_note`, `weekly_history`,
  `biggest_movers`) are pure functions over the stored rows.

## Views (design "Publication")

- **national**: only when the run is national. Ranked teams by national rank,
  tiers on; a ranked team outside the main island has no rank and is marked
  `comparable_nationally: false`.
- **conference**: ranked teams grouped by conference, each by its conference
  rank. No tiers. The view of every non-national run, whatever was asked for:
  a national request on such a run gets this view, with `publication.reason`.

## Absent is never zero

- `rank_change_7d` / `rating_change_7d` are null when there is no run 7 days
  before the latest one, or the team was not in it. Movement is measured
  against the run users saw a week before the latest run was computed, so it is
  fixed for a run, and the payload can be cached by run id.
- Teams under `MIN_MATCHES` are `unranked`, with the `needed` count, never placed.
- No run yet is an answer (`teams: []` and a `reason`), not an error.
"""

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, NamedTuple

import structlog
from pydantic import BaseModel

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import ToolError, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index
from mt_tools.leaderboards import _age_group, _InvalidArgsError, _leagues, _season
from mt_tools.power_rating import MIN_MATCHES, TIERS

logger = structlog.get_logger()

MOVEMENT_DAYS = 7
MOVERS = 3
UNAVAILABLE = "The Power Rating is unavailable right now."
CONFERENCES_MEET = "Conferences meet only at Flex and national events."

View = Literal["national", "conference"]
VIEWS: tuple[View, ...] = ("national", "conference")


# --- result models -----------------------------------------------------------


class RunRef(BaseModel):
    id: int
    computed_at: datetime
    through_date: date | None = None  # the latest rated match; null when nothing was rated
    matches_counted: int
    params_version: str


class MovementRef(BaseModel):
    """The run movement is measured from: the one users saw 7 days before `run`."""

    run_id: int
    computed_at: datetime


class PublicationState(BaseModel):
    national: bool
    reason: str | None = None  # why there is no national list; null when there is


class TierRef(BaseModel):
    key: str
    label: str
    min: int


class RankingsCoverage(BaseModel):
    teams_in_pool: int  # teams with at least one rated match in the run
    ranked: int
    unranked_count: int
    matches_counted: int
    matches_excluded: dict[str, int]
    min_matches: int = MIN_MATCHES
    note: str


class RankedTeam(BaseModel):
    rank: int | None  # national rank; null in the conference view and outside the main island
    team_id: int
    team: str
    club_id: int | None = None
    club_logo_url: str | None = None
    rating: int
    # Places moved in this view's rank (national, or conference), up is positive.
    # Null when there was no run a week earlier or the team had no such rank in it.
    rank_change_7d: int | None = None
    rating_change_7d: int | None = None
    w: int
    d: int
    l: int
    mp: int
    conference: str | None = None
    conference_rank: int | None = None
    tier: str | None = None  # national view only
    badges: list[str]
    xconf_mp: int
    pro_academy: bool = False
    comparable_nationally: bool = False


class UnrankedTeam(BaseModel):
    team_id: int
    team: str
    club_id: int | None = None
    club_logo_url: str | None = None
    conference: str | None = None
    mp: int
    needed: int = MIN_MATCHES


class PowerRatingResult(BaseModel):
    """One age group's Power Rating, from its latest run.

    `teams` [] with `reason` when there is no run or nothing was rated; null with
    `error` when MT could not check.
    """

    league: str
    age_group: str | None = None
    season: str | None = None
    view: View | None = None  # the view served, which may not be the one asked for
    conference: str | None = None  # the conference filter applied
    conferences: list[str] = []  # every conference in the run: the tabs, and what `conference` accepts
    run: RunRef | None = None
    movement_since: MovementRef | None = None
    publication: PublicationState | None = None
    coverage: RankingsCoverage | None = None
    tiers: list[TierRef] = []
    teams: list[RankedTeam] | None = None
    unranked: list[UnrankedTeam] | None = None
    reason: str | None = None
    error: ToolError | None = None


class HistoryPoint(BaseModel):
    run_id: int
    computed_at: datetime
    through_date: date | None = None
    rating: int
    rank: int | None = None
    conference_rank: int | None = None


class MatchMove(BaseModel):
    """One rated match, from the team's side."""

    match_id: int
    match_date: date | None = None  # null if the match row is gone
    opponent_id: int
    opponent: str
    result: Literal["W", "D", "L"]  # a shoot-out is a draw
    goals_for: int | None = None
    goals_against: int | None = None
    penalties_for: int | None = None
    penalties_against: int | None = None
    expected: float  # the share of the points the team was expected to take
    delta: float


class ScheduleStrength(BaseModel):
    rating: int  # mean opponent rating before each rated match
    rank: int | None = None  # toughest first; null when the team is unranked
    of: int | None = None
    scope: Literal["national", "conference"] | None = None


class PowerRatingTeamResult(BaseModel):
    """One team in the latest run: where it stands and why it moved.

    `in_run` false with `reason` when the team has no rated match in it (or there
    is no run): an answer, not an error.
    """

    league: str
    age_group: str | None = None
    season: str | None = None
    team_id: int
    team: str | None = None
    club_id: int | None = None
    club_logo_url: str | None = None
    pro_academy: bool = False
    run: RunRef | None = None
    in_run: bool = False
    rating: int | None = None
    rank: int | None = None
    conference: str | None = None
    conference_rank: int | None = None
    tier: str | None = None
    badges: list[str] = []
    ranked: bool = False
    needed: int | None = None  # matches still needed to be ranked; null once ranked
    mp: int | None = None
    w: int | None = None
    d: int | None = None
    l: int | None = None
    xconf_mp: int | None = None
    sos: ScheduleStrength | None = None
    biggest_movers: list[MatchMove] | None = None  # largest |delta| first, at most 3
    deltas: list[MatchMove] | None = None  # every rated match, oldest first
    history: list[HistoryPoint] | None = None  # one point per week: the week's last run
    reason: str | None = None
    error: ToolError | None = None


# --- pure building -------------------------------------------------------------


class TeamInfo(NamedTuple):
    name: str
    club_id: int | None = None
    logo_url: str | None = None
    pro_academy: bool = False


def _moment(value: Any) -> datetime:
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 'es' if word.endswith('ch') else 's'}"


def tier_refs() -> list[TierRef]:
    return [TierRef(key=key, label=label, min=int(minimum)) for key, label, minimum in TIERS]


def run_ref(run: Mapping[str, Any]) -> RunRef:
    return RunRef(
        id=run["id"],
        computed_at=run["computed_at"],
        through_date=run.get("through_date"),
        matches_counted=run.get("matches_counted") or 0,
        params_version=run.get("params_version") or "",
    )


def coverage_note(
    teams_in_pool: int, ranked: int, matches_counted: int, league: str, age_group: str, *, national_view: bool
) -> str:
    """The denominator, in words (root CLAUDE.md rule 3)."""
    text = (
        f"MT Power Rating from {_plural(teams_in_pool, f'{league} {age_group} team')} in MT, "
        f"rated on {_plural(matches_counted, 'match')}; {ranked} with {MIN_MATCHES} or more matches "
        f"{'is' if ranked == 1 else 'are'} ranked. {CONFERENCES_MEET}"
    )
    if not national_view:
        text += " Shown as conference lists: not yet comparable nationally."
    return text


def _conference_names(payload: Mapping[str, Any]) -> dict[int, str]:
    names = {str(k): v for k, v in (payload.get("conferences") or {}).items()}
    return {
        r["team_id"]: names[str(r["conference_division_id"])]
        for r in payload.get("ratings") or []
        if r.get("conference_division_id") is not None and str(r["conference_division_id"]) in names
    }


def _pick_conference(wanted: str | None, available: Iterable[str]) -> str | None:
    if wanted is None:
        return None
    options = sorted(set(available))
    found = next((c for c in options if c.casefold() == wanted.strip().casefold()), None)
    if found is None:
        raise _InvalidArgsError(f"conference must be one of {', '.join(options) or '(none in this run)'}.")
    return found


def build_rankings(
    payload: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    teams: Mapping[int, TeamInfo],
    *,
    league: str,
    age_group: str,
    season: str,
    view: View | None = None,
    conference: str | None = None,
) -> PowerRatingResult:
    """The served lists from a run payload (`PowerRatingDAO.run_payload`) and the run a week before it.

    Teams missing from `teams` (test content, or since deleted) are left out.
    Raises `_InvalidArgsError` for a conference the run does not have.
    """
    run = payload["run"]
    national_run = bool(run.get("national"))
    served: View = "national" if national_run and view in (None, "national") else "conference"
    conferences = _conference_names(payload)
    ratings = [r for r in payload.get("ratings") or [] if r["team_id"] in teams]
    chosen = _pick_conference(conference, conferences.values())

    prev_rows = {r["team_id"]: r for r in (previous or {}).get("ratings") or []}
    prev_conferences = _conference_names(previous) if previous else {}

    def change(r: Mapping[str, Any]) -> tuple[int | None, int | None]:
        before = prev_rows.get(r["team_id"])
        if before is None:
            return None, None
        rating_change = round(r["rating"]) - round(before["rating"])
        if served == "national":
            now_rank, then_rank = r.get("rank"), before.get("rank")
        elif conferences.get(r["team_id"]) == prev_conferences.get(r["team_id"]):
            now_rank, then_rank = r.get("conference_rank"), before.get("conference_rank")
        else:
            now_rank = then_rank = None
        rank_change = then_rank - now_rank if now_rank is not None and then_rank is not None else None
        return rank_change, rating_change

    ranked_rows, unranked_rows = [], []
    for r in ratings:
        info = teams[r["team_id"]]
        conf = conferences.get(r["team_id"])
        if chosen is not None and conf != chosen:
            continue
        if r["mp"] < MIN_MATCHES:
            unranked_rows.append(
                UnrankedTeam(
                    team_id=r["team_id"],
                    team=info.name,
                    club_id=info.club_id,
                    club_logo_url=info.logo_url,
                    conference=conf,
                    mp=r["mp"],
                )
            )
            continue
        rank_change, rating_change = change(r)
        ranked_rows.append(
            RankedTeam(
                rank=r.get("rank") if served == "national" else None,
                team_id=r["team_id"],
                team=info.name,
                club_id=info.club_id,
                club_logo_url=info.logo_url,
                rating=round(r["rating"]),
                rank_change_7d=rank_change,
                rating_change_7d=rating_change,
                w=r["w"],
                d=r["d"],
                l=r["l"],
                mp=r["mp"],
                conference=conf,
                conference_rank=r.get("conference_rank"),
                tier=r.get("tier") if served == "national" else None,
                badges=list(r.get("badges") or []),
                xconf_mp=r.get("xconf_mp") or 0,
                pro_academy=info.pro_academy,
                comparable_nationally=national_run and r.get("rank") is not None,
            )
        )

    if served == "national":
        ranked_rows.sort(key=lambda t: (t.rank is None, t.rank or 0, -t.rating, t.team_id))
    else:
        ranked_rows.sort(
            key=lambda t: (
                t.conference is None,
                (t.conference or "").casefold(),
                t.conference_rank is None,
                t.conference_rank or 0,
                -t.rating,
                t.team_id,
            )
        )
    unranked_rows.sort(key=lambda t: (-t.mp, t.team.casefold(), t.team_id))

    in_pool = len(ratings)
    ranked_count = sum(1 for r in ratings if r["mp"] >= MIN_MATCHES)
    matches_counted = run.get("matches_counted") or 0
    previous_run = (previous or {}).get("run")
    return PowerRatingResult(
        league=league,
        age_group=age_group,
        season=season,
        view=served,
        conference=chosen,
        conferences=sorted(set(conferences.values()), key=str.casefold),
        run=run_ref(run),
        movement_since=MovementRef(run_id=previous_run["id"], computed_at=previous_run["computed_at"])
        if previous_run
        else None,
        publication=PublicationState(national=national_run, reason=run.get("publication_reason")),
        coverage=RankingsCoverage(
            teams_in_pool=in_pool,
            ranked=ranked_count,
            unranked_count=in_pool - ranked_count,
            matches_counted=matches_counted,
            matches_excluded=dict(run.get("matches_excluded") or {}),
            note=coverage_note(
                in_pool, ranked_count, matches_counted, league, age_group, national_view=served == "national"
            ),
        ),
        tiers=tier_refs() if served == "national" else [],
        teams=ranked_rows,
        unranked=unranked_rows,
        reason=None if ratings else f"No rated matches at {age_group} {league} in {season} yet.",
    )


def no_run(league: str, age_group: str, season: str) -> PowerRatingResult:
    reason = f"No Power Rating has been computed for {league} {age_group} in {season} yet."
    return PowerRatingResult(
        league=league,
        age_group=age_group,
        season=season,
        publication=PublicationState(national=False, reason=reason),
        teams=[],
        unranked=[],
        reason=reason,
    )


def weekly_history(runs: Iterable[Mapping[str, Any]], ratings: Iterable[Mapping[str, Any]]) -> list[HistoryPoint]:
    """One point per ISO week, the week's last run, oldest first. A run without the team adds no point."""
    by_run = {r["run_id"]: r for r in ratings}
    last_of_week: dict[tuple[int, int], Mapping[str, Any]] = {}
    for run in sorted(runs, key=lambda r: (_moment(r["computed_at"]), r["id"])):
        if run["id"] in by_run:
            year, week, _ = _moment(run["computed_at"]).isocalendar()
            last_of_week[(year, week)] = run
    points = []
    for _, run in sorted(last_of_week.items()):
        r = by_run[run["id"]]
        points.append(
            HistoryPoint(
                run_id=run["id"],
                computed_at=run["computed_at"],
                through_date=run.get("through_date"),
                rating=round(r["rating"]),
                rank=r.get("rank"),
                conference_rank=r.get("conference_rank"),
            )
        )
    return points


def match_moves(
    deltas: Iterable[Mapping[str, Any]], matches: Mapping[int, Mapping[str, Any]], teams: Mapping[int, TeamInfo]
) -> list[MatchMove]:
    """Every rated match from the team's side, oldest first."""
    out = []
    for d in deltas:
        m = matches.get(d["match_id"]) or {}
        home = m.get("home_team_id") == d["team_id"]
        own, other = ("home", "away") if home else ("away", "home")
        result = d["result"]
        opponent = teams.get(d["opponent_id"])
        out.append(
            MatchMove(
                match_id=d["match_id"],
                match_date=m.get("match_date"),
                opponent_id=d["opponent_id"],
                opponent=opponent.name if opponent else str(d["opponent_id"]),
                result="W" if result == 1 else "D" if result == 0.5 else "L",
                goals_for=m.get(f"{own}_score") if m else None,
                goals_against=m.get(f"{other}_score") if m else None,
                penalties_for=m.get(f"{own}_penalty_score") if m else None,
                penalties_against=m.get(f"{other}_penalty_score") if m else None,
                expected=round(d["expected"], 3),
                delta=round(d["delta"], 1),
            )
        )
    out.sort(key=lambda x: (x.match_date is None, x.match_date or date.min, x.match_id))
    return out


def biggest_movers(moves: Iterable[MatchMove], n: int = MOVERS) -> list[MatchMove]:
    return sorted(moves, key=lambda x: (-abs(x.delta), x.match_id))[:n]


def schedule_strength(row: Mapping[str, Any], payload: Mapping[str, Any]) -> ScheduleStrength | None:
    """The team's SOS, ranked toughest first among the teams it can be compared with.

    National run and nationally ranked: among nationally ranked teams. Otherwise
    among ranked teams of its conference: islands are not on one scale.
    """
    if row.get("sos") is None:
        return None
    rating = round(row["sos"])
    if row["mp"] < MIN_MATCHES:
        return ScheduleStrength(rating=rating)
    ratings = [r for r in payload.get("ratings") or [] if r["mp"] >= MIN_MATCHES and r.get("sos") is not None]
    if payload["run"].get("national") and row.get("rank") is not None:
        scope: Literal["national", "conference"] = "national"
        peers = [r for r in ratings if r.get("rank") is not None]
    else:
        division = row.get("conference_division_id")
        if division is None:
            return ScheduleStrength(rating=rating)
        scope = "conference"
        peers = [r for r in ratings if r.get("conference_division_id") == division]
    toughest = sorted(peers, key=lambda r: (-r["sos"], r["team_id"]))
    rank = next(i for i, r in enumerate(toughest, start=1) if r["team_id"] == row["team_id"])
    return ScheduleStrength(rating=rating, rank=rank, of=len(peers), scope=scope)


def build_team(
    team_id: int,
    payload: Mapping[str, Any],
    runs: Iterable[Mapping[str, Any]],
    history_ratings: Iterable[Mapping[str, Any]],
    deltas: Iterable[Mapping[str, Any]],
    matches: Iterable[Mapping[str, Any]],
    teams: Mapping[int, TeamInfo],
    *,
    league: str,
    age_group: str,
    season: str,
) -> PowerRatingTeamResult:
    info = teams.get(team_id) or TeamInfo(name=str(team_id))
    base = {
        "league": league,
        "age_group": age_group,
        "season": season,
        "team_id": team_id,
        "team": info.name,
        "club_id": info.club_id,
        "club_logo_url": info.logo_url,
        "pro_academy": info.pro_academy,
        "run": run_ref(payload["run"]),
    }
    row = next((r for r in payload.get("ratings") or [] if r["team_id"] == team_id), None)
    if row is None:
        return PowerRatingTeamResult(
            **base,
            in_run=False,
            reason=f"{info.name} has no rated match at {age_group} {league} in {season}.",
        )
    moves = match_moves(deltas, {m["id"]: m for m in matches}, teams)
    ranked = row["mp"] >= MIN_MATCHES
    return PowerRatingTeamResult(
        **base,
        in_run=True,
        rating=round(row["rating"]),
        rank=row.get("rank"),
        conference=_conference_names(payload).get(team_id),
        conference_rank=row.get("conference_rank"),
        tier=row.get("tier"),
        badges=list(row.get("badges") or []),
        ranked=ranked,
        needed=None if ranked else MIN_MATCHES - row["mp"],
        mp=row["mp"],
        w=row["w"],
        d=row["d"],
        l=row["l"],
        xconf_mp=row.get("xconf_mp") or 0,
        sos=schedule_strength(row, payload),
        biggest_movers=biggest_movers(moves),
        deltas=moves,
        history=weekly_history(runs, history_ratings),
    )


# --- gathering -----------------------------------------------------------------


def _team_info(index: TeamIndex) -> dict[int, TeamInfo]:
    out = {}
    for team_id, team in index.teams.items():
        club = index.clubs.get(team.get("club_id") or 0) or {}
        out[team_id] = TeamInfo(
            name=str(team.get("name") or team_id),
            club_id=team.get("club_id"),
            logo_url=club.get("logo_url") or None,
            pro_academy=bool(club.get("pro_academy")),
        )
    return out


class _Scope(NamedTuple):
    league_id: int
    league: str
    age_group_id: int
    age_group: str
    season_id: int
    season: str
    index: TeamIndex


def _scope(deps: ToolDeps, league: str, age_group: str, season: str | None, today: date) -> _Scope:
    season_ref = _season(deps, season, today)
    index = load_team_index(deps, Viewer(include_test=False))
    league_row, _, _ = _leagues(index, league)
    age = _age_group(index, age_group)
    name = str(league_row.get("name"))
    return _Scope(league_row["id"], name, age.id, age.name, season_ref.id, season_ref.name, index)


def _payload(store, run_id: int) -> dict:
    payload = store.run_payload(run_id)
    if payload is None:
        raise DataUnavailableError(f"run {run_id} vanished")
    return payload


def get_power_rating(
    deps: ToolDeps,
    age_group: str,
    league: str = "Homegrown",
    season: str | None = None,
    *,
    view: str | None = None,
    conference: str | None = None,
    today: date | None = None,
) -> PowerRatingResult:
    """The latest Power Rating run for `league` at `age_group`, as national or conference lists.

    `season` is a season name ("2026-2027"); default the current season. `view`
    "national" is served only when the run is national.
    """

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> PowerRatingResult:
        return PowerRatingResult(league=league, error=ToolError(kind=kind, message=message))

    if view is not None and view not in VIEWS:
        return fail("invalid_args", f"view must be one of {', '.join(VIEWS)}.")
    store = deps.power_rating
    try:
        if store is None:
            raise DataUnavailableError("no power rating source")
        s = _scope(deps, league, age_group, season, today or date.today())
        latest = store.latest_run(s.season_id, s.age_group_id, s.league_id)
        if latest is None:
            return no_run(s.league, s.age_group, s.season)
        payload = _payload(store, latest["id"])
        since = _moment(latest["computed_at"]) - timedelta(days=MOVEMENT_DAYS)
        previous_run = store.run_as_of(s.season_id, s.age_group_id, s.league_id, since)
        previous = _payload(store, previous_run["id"]) if previous_run else None
        result = build_rankings(
            payload,
            previous,
            _team_info(s.index),
            league=s.league,
            age_group=s.age_group,
            season=s.season,
            view=view,  # type: ignore[arg-type]
            conference=conference,
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("power_rating_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_power_rating failed")
        return fail("unavailable", UNAVAILABLE)
    logger.info(
        "power_rating_served",
        league=result.league,
        age_group=result.age_group,
        run_id=result.run.id if result.run else None,
        view=result.view,
        teams=len(result.teams or []),
    )
    return result


def get_power_rating_team(
    deps: ToolDeps,
    team_id: int,
    age_group: str,
    league: str = "Homegrown",
    season: str | None = None,
    *,
    today: date | None = None,
) -> PowerRatingTeamResult:
    """One team in the latest run: rating, ranks, SOS, its biggest movers and its weekly history."""

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> PowerRatingTeamResult:
        return PowerRatingTeamResult(league=league, team_id=team_id, error=ToolError(kind=kind, message=message))

    store = deps.power_rating
    try:
        if store is None:
            raise DataUnavailableError("no power rating source")
        s = _scope(deps, league, age_group, season, today or date.today())
        teams = _team_info(s.index)
        if team_id not in teams:
            raise _InvalidArgsError(f"No team with id {team_id}.")
        latest = store.latest_run(s.season_id, s.age_group_id, s.league_id)
        if latest is None:
            info = teams[team_id]
            return PowerRatingTeamResult(
                league=s.league,
                age_group=s.age_group,
                season=s.season,
                team_id=team_id,
                team=info.name,
                club_id=info.club_id,
                club_logo_url=info.logo_url,
                pro_academy=info.pro_academy,
                reason=no_run(s.league, s.age_group, s.season).reason,
            )
        payload = _payload(store, latest["id"])
        in_run = any(r["team_id"] == team_id for r in payload.get("ratings") or [])
        runs = history = deltas = matches = []
        if in_run:
            runs = store.runs(s.season_id, s.age_group_id, s.league_id)
            history = store.team_ratings(team_id, [r["id"] for r in runs])
            deltas = store.team_deltas(latest["id"], team_id)
            matches = store.matches_by_ids(d["match_id"] for d in deltas)
        return build_team(
            team_id,
            payload,
            runs,
            history,
            deltas,
            matches,
            teams,
            league=s.league,
            age_group=s.age_group,
            season=s.season,
        )
    except _InvalidArgsError as exc:
        return fail("invalid_args", str(exc))
    except DataUnavailableError as exc:
        logger.warning("power_rating_team_unavailable", error=str(exc))
        return fail("unavailable", UNAVAILABLE)
    except Exception:
        logger.exception("get_power_rating_team failed")
        return fail("unavailable", UNAVAILABLE)
