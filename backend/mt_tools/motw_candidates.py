"""Match of the Week candidates: which fixtures this week are worth featuring (SB-1550).

Two layers, so the scoring is testable without a database:

- **Gathering** (`suggest_motw_candidates`) reads the pool's fixtures, results and
  standings through the same DAO protocols MT AI uses (`ToolDeps`), plus the
  recent Match of the Week picks.
- **Scoring** (`score_fixture`, `team_strengths`, `form_score`, `build_facts`...) is
  pure functions over plain dicts.

## Pool

`POOL` names the leagues, conferences, age groups and match types the suggestion
draws from. Names are resolved against the divisions MT actually has; a name that
does not resolve is an error, not a silently smaller pool.

Eligible: League or Flex, status scheduled/tbd, not test, dated in the target week
(Monday-Sunday) and not before today.

## Score (v1 weights)

    total = 0.40 quality + 0.25 closeness + 0.20 stakes + 0.15 form   (x 0.5 if recently featured)

- **strength** of a team is its percentile in its own table (the one the fixture
  counts in) on points per game and goal difference per game, averaged. A
  percentile, so a U15 and a U19 table compare on equal terms. Fewer than 3 games
  played damps strength towards 0.5 and flags `low_sample`. A team with no row
  has not played a counted match: strength 0.5, `low_sample`.
- **quality** = the weaker team's strength: a great match needs two good teams.
- **closeness** = 1 - |strength difference|.
- **stakes** = the strongest of: adjacent in the table, both near the top, and both
  in contention at a rank a qualification rule selects (Flex conference winner).
  Only a rule from `qualification_rules` creates a "line"; a Homegrown league
  table has none, because no source ties a league finish to a Cup place.
- **form** = both teams' last five League/Flex results, newest weighted most,
  win 1 / draw 0.5 / loss 0, averaged. No results → 0.5.

## Facts

Each candidate carries facts with stable ids (`<match_id>:<slug>`) - table position,
points gap, streaks, scoring rate, earlier meeting, common opponents, games left,
and the qualification rules its table feeds. The agent writing "Why this is the
Match of the Week" must cite a fact id for every reason. Player facts are not
produced: goals are user data, tracked for few teams, and absent is never zero.

Coverage is always reported: how many fixtures the pool had this week, how many
were eligible, and how many teams had too few games to judge.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.schemas import AgeGroupRef, DivisionRef, SeasonRef, TeamRef, ToolError, Viewer
from mt_ai.tools.visibility import DataUnavailableError, TeamIndex, load_team_index
from mt_tools.qualification_rules import (
    QualificationRule,
    RulesError,
    conference_kind,
    load_rules,
    season_key,
    tier_of,
)

logger = structlog.get_logger()

POOL_TIMEZONE = ZoneInfo("America/New_York")

WEIGHTS: dict[str, float] = {"quality": 0.40, "closeness": 0.25, "stakes": 0.20, "form": 0.15}
FEATURED_PENALTY = 0.5  # multiplier for a team picked in the last FEATURED_WEEKS weeks
FEATURED_WEEKS = 2
LOW_SAMPLE_GAMES = 3
FORM_GAMES = 5
FORM_WEIGHTS = (5, 4, 3, 2, 1)  # newest first
LINE_MARGIN_POINTS = 3  # "in contention" for a ranked place: within this many points of it
MAX_LIMIT = 10

ELIGIBLE_STATUSES = frozenset({"scheduled", "tbd"})
PLAYED_STATUSES = frozenset({"completed", "forfeit"})
OPEN_STATUSES = frozenset({"scheduled", "tbd", "postponed"})

FactKind = Literal["standings", "form", "stakes", "rivalry", "storyline"]


@dataclass(frozen=True)
class Pool:
    age_groups: tuple[str, ...]
    match_types: tuple[str, ...]
    # (league, division) pairs, as MT names them.
    conferences: tuple[tuple[str, str], ...]


POOL = Pool(
    age_groups=("U15", "U16", "U17", "U19"),
    match_types=("League", "Flex"),
    conferences=(
        ("Homegrown", "Northeast"),
        ("Homegrown", "Northeast (Pro Player Pathway)"),
        ("Flex", "Empire"),
        ("Flex", "New England"),
        ("Flex", "Turnpike"),
    ),
)


class PoolConfigError(Exception):
    """The pool names a league/division MT does not have."""


# --- result models -----------------------------------------------------------


class MotwFact(BaseModel):
    """One thing that is true about a candidate, with an id a reason can cite."""

    id: str
    kind: FactKind
    text: str
    team_id: int | None = None
    rule_id: str | None = None
    # For a fact stated from a qualification rule: whether that rule is confirmed.
    # An unconfirmed rule may only be repeated as unconfirmed.
    confirmed: bool | None = None


class CandidateTeam(TeamRef):
    position: int | None = None  # null: no row in the table yet
    table_size: int | None = None
    played: int = 0
    points: int | None = None
    strength: float
    form: float | None = None  # null: no League/Flex results yet
    low_sample: bool = False


class ScoreBreakdown(BaseModel):
    quality: float
    closeness: float
    stakes: float
    form: float
    penalty: float = 1.0
    total: float


class RuleRef(BaseModel):
    id: str
    pathway: str
    confirmed: bool
    summary: str
    source_url: str | None = None


class MotwCandidate(BaseModel):
    match_id: int
    match_date: date
    scheduled_kickoff: str | None = None
    age_group: AgeGroupRef
    division: DivisionRef
    competition: str
    home: CandidateTeam
    away: CandidateTeam
    score: ScoreBreakdown
    flags: list[str] = []
    facts: list[MotwFact] = []
    rules: list[RuleRef] = []


class CurrentPick(BaseModel):
    match_id: int
    blurb: str | None = None
    has_reasons: bool = False


class CandidatesCoverage(BaseModel):
    divisions: int
    fixtures_in_week: int  # every pool fixture dated in the week, any status
    eligible: int  # still to be played, League/Flex, not before today
    teams_low_sample: int
    rules_season: str | None = None  # null: no rules file for this season


class MotwCandidatesResult(BaseModel):
    """Ranked candidates for one week.

    `candidates` is [] with `reason` when the week has nothing eligible, and null
    with `error` when MT could not check. `current_pick` is the week's pick if one
    exists: candidates are still returned, but an agent must not overwrite a pick.
    """

    week_start: date
    week_end: date
    today: date | None = None
    season: SeasonRef | None = None
    current_pick: CurrentPick | None = None
    candidates: list[MotwCandidate] | None = None
    reason: str | None = None
    coverage: CandidatesCoverage | None = None
    weights: dict[str, float] = WEIGHTS
    error: ToolError | None = None


# --- pure scoring --------------------------------------------------------------


@dataclass(frozen=True)
class TeamStanding:
    team_id: int
    position: int
    played: int
    points: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int


def standings_from_rows(rows: list[dict]) -> dict[int, TeamStanding]:
    """`MatchDAO.get_standings` rows (already in table order) by team id."""
    out: dict[int, TeamStanding] = {}
    for position, row in enumerate(rows, start=1):
        team_id = row.get("team_id")
        if team_id is None:
            continue
        out[team_id] = TeamStanding(
            team_id=team_id,
            position=position,
            played=row.get("played") or 0,
            points=row.get("points") or 0,
            wins=row.get("wins") or 0,
            draws=row.get("draws") or 0,
            losses=row.get("losses") or 0,
            goals_for=row.get("goals_for") or 0,
            goals_against=row.get("goals_against") or 0,
        )
    return out


def _percentiles(values: dict[int, float]) -> dict[int, float]:
    """Rank percentile in [0, 1], ties sharing their average rank; one team → 0.5."""
    n = len(values)
    if n == 0:
        return {}
    if n == 1:
        return dict.fromkeys(values, 0.5)
    ordered = sorted(values.values())
    out = {}
    for key, value in values.items():
        below = sum(1 for v in ordered if v < value)
        equal = sum(1 for v in ordered if v == value)
        out[key] = (below + (equal - 1) / 2) / (n - 1)
    return out


def team_strengths(table: dict[int, TeamStanding]) -> dict[int, tuple[float, bool]]:
    """team_id → (strength in [0, 1], low_sample) for every team with a row."""
    played = {t: s for t, s in table.items() if s.played > 0}
    ppg = _percentiles({t: s.points / s.played for t, s in played.items()})
    gdpg = _percentiles({t: (s.goals_for - s.goals_against) / s.played for t, s in played.items()})
    out: dict[int, tuple[float, bool]] = {}
    for team_id, standing in table.items():
        if team_id not in played:
            out[team_id] = (0.5, True)
            continue
        raw = (ppg[team_id] + gdpg[team_id]) / 2
        if standing.played < LOW_SAMPLE_GAMES:
            out[team_id] = (0.5 + (raw - 0.5) * standing.played / LOW_SAMPLE_GAMES, True)
        else:
            out[team_id] = (raw, False)
    return out


def result_for(match: dict, team_id: int) -> Literal["W", "D", "L"] | None:
    """A played match's result from `team_id`'s side, on the regulation score."""
    if match.get("match_status") not in PLAYED_STATUSES:
        return None
    hs, as_ = match.get("home_score"), match.get("away_score")
    if hs is None or as_ is None:
        return None
    ours, theirs = (hs, as_) if match.get("home_team_id") == team_id else (as_, hs)
    return "W" if ours > theirs else "L" if ours < theirs else "D"


def team_results(matches: Iterable[dict], team_id: int, before: date) -> list[tuple[dict, str]]:
    """Played League/Flex matches of a team before `before`, newest first, with its result."""
    out = []
    for m in matches:
        if team_id not in (m.get("home_team_id"), m.get("away_team_id")):
            continue
        if m.get("match_type_name") not in POOL.match_types:
            continue
        if _date(m.get("match_date")) >= before:
            continue
        result = result_for(m, team_id)
        if result:
            out.append((m, result))
    out.sort(key=lambda r: (_date(r[0].get("match_date")), r[0].get("id") or 0), reverse=True)
    return out


def form_score(results: list[str]) -> float | None:
    """Recency-weighted form over the last five results (newest first); None if none."""
    recent = results[:FORM_GAMES]
    if not recent:
        return None
    value = {"W": 1.0, "D": 0.5, "L": 0.0}
    weights = FORM_WEIGHTS[: len(recent)]
    return sum(w * value[r] for w, r in zip(weights, recent, strict=True)) / sum(weights)


def stakes_score(
    home: TeamStanding | None, away: TeamStanding | None, table_size: int, line_ranks: Iterable[int], table: dict
) -> tuple[float, list[str]]:
    """How much the table says rides on it, in [0, 1], and why (flag names)."""
    if home is None or away is None or table_size < 2:
        return 0.0, []
    components: dict[str, float] = {}
    gap = abs(home.position - away.position)
    if gap == 1:
        components["adjacent"] = 0.7
    elif gap == 2:
        components["adjacent"] = 0.45
    top = max(home.position, away.position)
    if top <= 3:
        components["top_of_table"] = 1.0
    elif min(home.position, away.position) <= 2 and top <= 5:
        components["top_of_table"] = 0.7
    by_position = {s.position: s for s in table.values()}
    for rank in line_ranks:
        line = by_position.get(rank)
        if line is None:
            continue
        if all(t.points >= line.points - LINE_MARGIN_POINTS for t in (home, away)):
            components["qualifying_line"] = 1.0
    if not components:
        return 0.0, []
    best = max(components.values())
    return best, sorted(k for k, v in components.items() if v > 0)


def score_fixture(
    strength_home: float,
    strength_away: float,
    stakes: float,
    form_home: float | None,
    form_away: float | None,
    *,
    featured: bool,
) -> ScoreBreakdown:
    quality = min(strength_home, strength_away)
    closeness = 1 - abs(strength_home - strength_away)
    form = ((0.5 if form_home is None else form_home) + (0.5 if form_away is None else form_away)) / 2
    penalty = FEATURED_PENALTY if featured else 1.0
    total = (
        WEIGHTS["quality"] * quality
        + WEIGHTS["closeness"] * closeness
        + WEIGHTS["stakes"] * stakes
        + WEIGHTS["form"] * form
    ) * penalty
    return ScoreBreakdown(
        quality=round(quality, 3),
        closeness=round(closeness, 3),
        stakes=round(stakes, 3),
        form=round(form, 3),
        penalty=penalty,
        total=round(total, 4),
    )


# --- facts ---------------------------------------------------------------------


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def streak_text(name: str, results: list[str]) -> str | None:
    """A run of 3+ wins or unbeaten games from the newest result, or a perfect record."""
    if len(results) >= 3 and all(r == "W" for r in results):
        return f"{name} have won all {len(results)} of their League/Flex games this season."
    wins = 0
    for r in results:
        if r != "W":
            break
        wins += 1
    if wins >= 3:
        return f"{name} have won {wins} League/Flex games in a row."
    unbeaten = 0
    for r in results:
        if r == "L":
            break
        unbeaten += 1
    if unbeaten >= 3:
        return f"{name} are unbeaten in {unbeaten} League/Flex games."
    losses = 0
    for r in results:
        if r != "L":
            break
        losses += 1
    if losses >= 3:
        return f"{name} have lost {losses} in a row and need a result."
    return None


def build_facts(
    match: dict,
    table_label: str,
    table: dict[int, TeamStanding],
    names: dict[int, str],
    history: list[dict],
    today: date,
    rules: list[QualificationRule],
) -> list[MotwFact]:
    """Every fact about one fixture that the data supports. Pure."""
    mid = match["id"]
    home_id, away_id = match["home_team_id"], match["away_team_id"]
    facts: list[MotwFact] = []
    table_size = len(table)

    for side, team_id in (("home", home_id), ("away", away_id)):
        s = table.get(team_id)
        if s is None or s.played == 0:
            continue
        facts.append(
            MotwFact(
                id=f"{mid}:pos:{side}",
                kind="standings",
                team_id=team_id,
                text=(
                    f"{names[team_id]} are {_ordinal(s.position)} of {table_size} in {table_label} with "
                    f"{_plural(s.points, 'point')} from {_plural(s.played, 'game')} ({s.wins}-{s.draws}-{s.losses})."
                ),
            )
        )
        if s.played >= LOW_SAMPLE_GAMES:
            facts.append(
                MotwFact(
                    id=f"{mid}:rate:{side}",
                    kind="form",
                    team_id=team_id,
                    text=(
                        f"{names[team_id]} score {s.goals_for / s.played:.1f} and concede "
                        f"{s.goals_against / s.played:.1f} goals per game in {table_label}."
                    ),
                )
            )

    h, a = table.get(home_id), table.get(away_id)
    if h and a and h.played and a.played:
        gap = abs(h.points - a.points)
        text = (
            f"{names[home_id]} and {names[away_id]} are level on {_plural(h.points, 'point')}."
            if gap == 0
            else f"{_plural(gap, 'point')} separate {names[home_id]} ({h.points}) and {names[away_id]} ({a.points})."
        )
        facts.append(MotwFact(id=f"{mid}:gap", kind="standings", text=text))

    for side, team_id in (("home", home_id), ("away", away_id)):
        results = [r for _, r in team_results(history, team_id, today)]
        text = streak_text(names[team_id], results)
        if text:
            facts.append(MotwFact(id=f"{mid}:streak:{side}", kind="form", team_id=team_id, text=text))

    meetings = [
        m
        for m in history
        if {m.get("home_team_id"), m.get("away_team_id")} == {home_id, away_id}
        and m.get("id") != mid
        and result_for(m, home_id)
    ]
    if meetings:
        last = max(meetings, key=lambda m: _date(m.get("match_date")))
        facts.append(
            MotwFact(
                id=f"{mid}:h2h",
                kind="rivalry",
                text=(
                    f"They met on {_date(last['match_date']):%b %-d} ({last.get('match_type_name')}): "
                    f"{names.get(last['home_team_id'], last.get('home_team_name'))} {last['home_score']}-"
                    f"{last['away_score']} {names.get(last['away_team_id'], last.get('away_team_name'))}."
                ),
            )
        )

    common = _common_opponents(history, home_id, away_id, today)
    if len(common) >= 2:

        def record(team_id: int) -> str:
            rs = [r for opp in common for r in common[opp][team_id]]
            return f"{rs.count('W')}-{rs.count('D')}-{rs.count('L')}"

        facts.append(
            MotwFact(
                id=f"{mid}:common",
                kind="storyline",
                text=(
                    f"Against the {len(common)} opponents both have played, {names[home_id]} went "
                    f"{record(home_id)} and {names[away_id]} {record(away_id)}."
                ),
            )
        )

    for side, team_id in (("home", home_id), ("away", away_id)):
        left = sum(
            1
            for m in history
            if m.get("id") != mid
            and m.get("division_id") == match.get("division_id")
            and m.get("match_status") in OPEN_STATUSES
            and team_id in (m.get("home_team_id"), m.get("away_team_id"))
            and _date(m.get("match_date")) >= _date(match.get("match_date"))
        )
        if left:
            facts.append(
                MotwFact(
                    id=f"{mid}:left:{side}",
                    kind="stakes",
                    team_id=team_id,
                    text=f"{names[team_id]} have {_plural(left, 'game')} left in {table_label} after this one.",
                )
            )

    for rule in rules:
        prefix = "" if rule.confirmed else "Unconfirmed: "
        facts.append(
            MotwFact(
                id=f"{mid}:rule:{rule.id}",
                kind="stakes",
                rule_id=rule.id,
                confirmed=rule.confirmed,
                text=f"{prefix}{rule.competition} → {rule.pathway}. {rule.summary}",
            )
        )
    return facts


def _common_opponents(history: list[dict], home_id: int, away_id: int, today: date) -> dict[int, dict[int, list[str]]]:
    seen: dict[int, dict[int, list[str]]] = {}
    for team_id in (home_id, away_id):
        for m, r in team_results(history, team_id, today):
            opp = m["away_team_id"] if m["home_team_id"] == team_id else m["home_team_id"]
            if opp in (home_id, away_id):
                continue
            seen.setdefault(opp, {home_id: [], away_id: []})[team_id].append(r)
    return {opp: rs for opp, rs in seen.items() if rs[home_id] and rs[away_id]}


# --- gathering -----------------------------------------------------------------


@dataclass(frozen=True)
class PoolDivision:
    id: int
    name: str
    league: str
    age_groups: tuple[AgeGroupRef, ...]


def resolve_pool(index: TeamIndex, pool: Pool = POOL) -> list[PoolDivision]:
    """The pool's (league, division) names → MT divisions, with the pool ages each runs.

    Raises PoolConfigError naming every pair MT does not have.
    """
    found: dict[tuple[str, str], tuple[int, dict[int, AgeGroupRef]]] = {}
    for team in index.teams.values():
        for mapping in team.get("team_mappings") or []:
            division, age = mapping.get("divisions") or {}, mapping.get("age_groups") or {}
            league = index.leagues.get(division.get("league_id") or 0) or division.get("leagues") or {}
            key = (str(league.get("name") or ""), str(division.get("name") or ""))
            if key not in pool.conferences or division.get("id") is None:
                continue
            entry = found.setdefault(key, (division["id"], {}))
            if age.get("name") in pool.age_groups:
                entry[1][age["id"]] = AgeGroupRef(id=age["id"], name=age["name"])
    missing = [f"{league} / {name}" for league, name in pool.conferences if (league, name) not in found]
    if missing:
        raise PoolConfigError(f"MOTW pool names divisions MT does not have: {', '.join(missing)}")
    return [
        PoolDivision(id=div_id, name=name, league=league, age_groups=tuple(sorted(ages.values(), key=lambda a: a.name)))
        for (league, name), (div_id, ages) in found.items()
    ]


PickReader = Callable[[str], dict | None]


def week_bounds(week: str | date | None, today: date) -> tuple[date, date]:
    """Monday and Sunday of the week containing `week` (any date in it), default this week."""
    day = today if week is None else (week if isinstance(week, date) else date.fromisoformat(str(week)[:10]))
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def suggest_motw_candidates(
    deps: ToolDeps,
    week: str | date | None = None,
    *,
    picks: PickReader,
    limit: int = 5,
    now: datetime | None = None,
    pool: Pool = POOL,
) -> MotwCandidatesResult:
    """Top `limit` Match of the Week candidates for a week, public data only."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    today = current.astimezone(POOL_TIMEZONE).date()
    try:
        week_start, week_end = week_bounds(week, today)
    except ValueError:
        start = today - timedelta(days=today.weekday())
        return MotwCandidatesResult(
            week_start=start,
            week_end=start + timedelta(days=6),
            error=ToolError(kind="invalid_args", message="week must be a date (YYYY-MM-DD) in the week wanted."),
        )

    def fail(kind: Literal["unavailable", "invalid_args"], message: str) -> MotwCandidatesResult:
        return MotwCandidatesResult(
            week_start=week_start, week_end=week_end, today=today, error=ToolError(kind=kind, message=message)
        )

    if not 1 <= limit <= MAX_LIMIT:
        return fail("invalid_args", f"limit must be between 1 and {MAX_LIMIT}.")

    viewer = Viewer(include_test=False)
    try:
        season_row = deps.seasons.get_current_season()
        if not season_row:
            raise DataUnavailableError("no current season")
        season = SeasonRef(id=season_row["id"], name=season_row["name"])
        index = load_team_index(deps, viewer)
        divisions = resolve_pool(index, pool)
        history: dict[tuple[int, int], list[dict]] = {}
        for division in divisions:
            for age in division.age_groups:
                history[(division.id, age.id)] = deps.matches.get_all_matches(
                    season_id=season.id,
                    age_group_id=age.id,
                    division_id=division.id,
                    include_test=False,
                    raise_on_error=True,
                )
        current_pick = _current_pick(picks, week_start)
        featured = _recently_featured(picks, week_start)
    except PoolConfigError as exc:
        logger.error("motw_pool_config", error=str(exc))
        return fail("unavailable", str(exc))
    except DataUnavailableError as exc:
        return fail("unavailable", f"MOTW candidates are unavailable right now ({exc}).")
    except Exception:
        logger.exception("suggest_motw_candidates failed")
        return fail("unavailable", "MOTW candidates are unavailable right now.")

    rules_key = season_key(season.name)
    try:
        ruleset = load_rules(rules_key) if rules_key else None
    except RulesError:
        logger.warning("motw_no_rules", season=season.name)
        ruleset = None

    every = [m for ms in history.values() for m in ms]
    by_division = {d.id: d for d in divisions}
    in_week = [m for m in every if week_start <= _date(m.get("match_date")) <= week_end]
    eligible = [
        m
        for m in in_week
        if m.get("match_status") in ELIGIBLE_STATUSES
        and m.get("match_type_name") in pool.match_types
        and _date(m.get("match_date")) >= today
    ]

    candidates: list[MotwCandidate] = []
    low_sample_teams: set[int] = set()
    tables: dict[tuple[int, int], dict[int, TeamStanding]] = {}
    for match in eligible:
        division = by_division[match["division_id"]]
        key = (division.id, match["age_group_id"])
        try:
            if key not in tables:
                data = deps.matches.get_standings(
                    season_id=season.id,
                    age_group_id=match["age_group_id"],
                    division_id=division.id,
                    match_type=match["match_type_name"],
                    include_test=False,
                    raise_on_error=True,
                )
                tables[key] = standings_from_rows(data.get("standings") or [])
        except Exception:
            logger.exception("motw standings failed", division_id=division.id, age_group_id=match["age_group_id"])
            return fail("unavailable", "MOTW candidates are unavailable right now (standings).")
        # One team row plays every age group (a club in a league), so history is
        # scoped to the fixture's age group: IFA U16's form is not IFA U19's.
        age_history = [m for m in every if m.get("age_group_id") == match["age_group_id"]]
        candidate = _candidate(
            match, division, tables[key], age_history, index, today, featured, ruleset, low_sample_teams
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: (-c.score.total, c.match_date, c.match_id))
    coverage = CandidatesCoverage(
        divisions=len(divisions),
        fixtures_in_week=len(in_week),
        eligible=len(eligible),
        teams_low_sample=len(low_sample_teams),
        rules_season=ruleset.season if ruleset else None,
    )
    logger.info(
        "motw_candidates_scored",
        week_start=week_start.isoformat(),
        divisions=coverage.divisions,
        fixtures_in_week=coverage.fixtures_in_week,
        eligible=coverage.eligible,
        teams_low_sample=coverage.teams_low_sample,
        returned=min(limit, len(candidates)),
        candidates=[_score_log(c) for c in candidates],
    )
    reason = None
    if not candidates:
        reason = (
            f"No pool fixtures are dated {week_start:%b %-d}-{week_end:%b %-d}."
            if not in_week
            else f"None of the {len(in_week)} pool fixtures that week are still to be played."
        )
    return MotwCandidatesResult(
        week_start=week_start,
        week_end=week_end,
        today=today,
        season=season,
        current_pick=current_pick,
        candidates=candidates[:limit],
        reason=reason,
        coverage=coverage,
    )


def _score_log(c: MotwCandidate) -> dict[str, Any]:
    """Why a candidate ranked where it did. Every eligible fixture, so near misses show too."""
    return {
        "match_id": c.match_id,
        "fixture": f"{c.home.name} vs {c.away.name}",
        "age_group": c.age_group.name,
        "division": c.division.name,
        "competition": c.competition,
        **c.score.model_dump(),
        "flags": c.flags,
    }


def _candidate(
    match: dict,
    division: PoolDivision,
    table: dict[int, TeamStanding],
    history: list[dict],
    index: TeamIndex,
    today: date,
    featured: set[int],
    ruleset: Any,
    low_sample_teams: set[int],
) -> MotwCandidate:
    age = AgeGroupRef(id=match["age_group_id"], name=match.get("age_group_name") or "")
    competition = match.get("match_type_name") or ""
    label = f"{age.name} {division.name}" + (f" ({competition})" if competition != "League" else "")
    strengths = team_strengths(table)
    home_id, away_id = match["home_team_id"], match["away_team_id"]
    names = {
        home_id: match.get("home_team_name") or str(home_id),
        away_id: match.get("away_team_name") or str(away_id),
    }
    for m in history:
        names.setdefault(m["home_team_id"], m.get("home_team_name") or str(m["home_team_id"]))
        names.setdefault(m["away_team_id"], m.get("away_team_name") or str(m["away_team_id"]))

    kind = conference_kind(division.league, division.name)
    rules: list[QualificationRule] = (
        ruleset.applicable(age.name, kind, tier=tier_of(division.league)) if ruleset and kind else []
    )
    line_ranks = [r.selector.rank for r in rules if r.selector and r.selector.rank]

    teams: dict[str, CandidateTeam] = {}
    forms: dict[int, float | None] = {}
    flags: list[str] = []
    for side, team_id in (("home", home_id), ("away", away_id)):
        strength, low = strengths.get(team_id, (0.5, True))
        forms[team_id] = form_score([r for _, r in team_results(history, team_id, today)])
        standing = table.get(team_id)
        team = index.teams.get(team_id) or {}
        teams[side] = CandidateTeam(
            id=team_id,
            name=names[team_id],
            club_name=index.club_name(team) if team else None,
            position=standing.position if standing else None,
            table_size=len(table) or None,
            played=standing.played if standing else 0,
            points=standing.points if standing else None,
            strength=round(strength, 3),
            form=None if forms[team_id] is None else round(forms[team_id], 3),
            low_sample=low,
        )
        if low:
            low_sample_teams.add(team_id)
            if "low_sample" not in flags:
                flags.append("low_sample")

    stakes, stake_flags = stakes_score(table.get(home_id), table.get(away_id), len(table), line_ranks, table)
    flags.extend(stake_flags)
    is_featured = bool({home_id, away_id} & featured)
    if is_featured:
        flags.append("recently_featured")
    score = score_fixture(
        teams["home"].strength, teams["away"].strength, stakes, forms[home_id], forms[away_id], featured=is_featured
    )
    return MotwCandidate(
        match_id=match["id"],
        match_date=_date(match["match_date"]),
        scheduled_kickoff=match.get("scheduled_kickoff"),
        age_group=age,
        division=DivisionRef(id=division.id, name=division.name, league=division.league),
        competition=competition,
        home=teams["home"],
        away=teams["away"],
        score=score,
        flags=flags,
        facts=build_facts(match, label, table, names, history, today, rules),
        rules=[
            RuleRef(id=r.id, pathway=r.pathway, confirmed=r.confirmed, summary=r.summary, source_url=r.source_url)
            for r in rules
        ],
    )


def _current_pick(picks: PickReader, week_start: date) -> CurrentPick | None:
    pick = picks(week_start.isoformat())
    if not pick:
        return None
    match = pick.get("match") or {}
    return CurrentPick(
        match_id=match.get("id") or pick.get("match_id"),
        blurb=pick.get("blurb"),
        has_reasons=bool(pick.get("reasons")),
    )


def _recently_featured(picks: PickReader, week_start: date) -> set[int]:
    """Teams in the picks of the FEATURED_WEEKS weeks before this one."""
    teams: set[int] = set()
    for back in range(1, FEATURED_WEEKS + 1):
        pick = picks((week_start - timedelta(weeks=back)).isoformat())
        match = (pick or {}).get("match") or {}
        teams.update(t for t in (match.get("home_team_id"), match.get("away_team_id")) if t is not None)
    return teams


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def suggest_from_deps(
    deps: ToolDeps, week: str | None = None, *, limit: int = 5, now: datetime | None = None
) -> MotwCandidatesResult:
    """`suggest_motw_candidates` reading the picks from `deps.motw` (mt-mcp, the API)."""
    motw = deps.motw
    if motw is None:
        start, end = week_bounds(None, (now or datetime.now(UTC)).astimezone(POOL_TIMEZONE).date())
        return MotwCandidatesResult(
            week_start=start,
            week_end=end,
            error=ToolError(kind="unavailable", message="MOTW candidates are unavailable right now."),
        )
    return suggest_motw_candidates(deps, week, picks=lambda w: motw.get_for_week(w), limit=limit, now=now)
