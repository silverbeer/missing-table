"""MT Power Rating engine: Elo over one age group's season, plus a Massey audit (SB-1805).

Pure functions over plain dataclasses: no database, no I/O. Gathering the
matches, storing a run and serving it are later slices (SB-1784 design,
`docs/03-architecture/power-rating-engine.md`).

## The model (parameters approved 2026-11-27, `PARAMS_VERSION`)

    E     = 1 / (1 + 10^(-(R_team - R_opp + H) / 400))   H = +50 home, -50 away, 0 neutral
    S     = 1 win, 0.5 draw (a shoot-out is a draw), 0 loss
    new R = R + K * G * (S - E)
    K     = 30 for every competition; 60 for a team's first 8 rated matches
    G     = 1 for a draw or 1-goal margin, 1.5 for 2, 1.75 for 3 or more (cap)

The exchange is equal and opposite unless one side is still on provisional K.
Ratings start at 1500, or at a carried-over rating (`carry_over`).

## What is rated

Regulation scores only: a shoot-out is a draw. A match is **not rated**, and is
counted in `matches_excluded`, when it was a forfeit (no football was played) or
either side is out of pool (no Homegrown conference at this age group). The
caller passes only completed matches in which both sides fielded this age group.

## Order

Chronological by `match_date`, then `kickoff_time` (a match with no kickoff time
goes after the timed ones that day), then `match_id`. Every run replays the
season from its first match, so a corrected result lands in date order.

## Publication

An age group gets a national list only when one island (teams connected by
rated matches) holds at least 90% of ranked teams **and** every conference in
it has at least 5 matches against other conferences. Otherwise it is shown as
conference lists only, and no team carries a tier. Teams with fewer than
`MIN_MATCHES` rated matches are unranked: listed, never placed.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, time
from typing import Literal

import numpy as np

from mt_tools.leaderboards import TeamTally, conference_of

PARAMS_VERSION = "elo-v1"

START_RATING = 1500.0
SCALE = 400.0
K = 30.0
PROVISIONAL_MATCHES = 8  # K x PROVISIONAL_K_MULT for a team's first 8 rated matches
PROVISIONAL_K_MULT = 2.0
HOME_ADVANTAGE = 50.0  # in the expected score only; 0 at a neutral venue
MARGIN_CAP = 3
ROLLOVER_CARRY = 0.3  # new season start = 1500 + 0.3 * (last final - 1500)

MIN_MATCHES = 6  # ranked from this many rated matches
LOW_CROSS_CONFERENCE = 3  # flagged under this many matches against other conferences

NATIONAL_ISLAND_SHARE = 0.9
NATIONAL_MIN_CROSS_CONFERENCE = 5

MASSEY_CAP = 4
MASSEY_RIDGE = 1.0
RANK_GAP_FLAG = 30  # Elo vs Massey places, about the worst 5% at the 2026-11-26 freeze

Competition = Literal["league", "flex", "tournament", "cup"]
NEUTRAL_COMPETITIONS = frozenset({"tournament", "cup"})

# (key, label, minimum rating). Below the last: no label.
TIERS: tuple[tuple[str, str, float], ...] = (
    ("elite", "Elite", 1700.0),
    ("contender", "Contender", 1600.0),
    ("above_average", "Above average", 1500.0),
)

EXCLUSION_REASONS = ("forfeit", "out_of_pool_opponent")


# --- input ---------------------------------------------------------------------


@dataclass(frozen=True)
class RatedMatch:
    """One completed match at the age group, as the gatherer read it.

    `conference` is the Homegrown conference (division) of a League match, None
    for Flex and tournaments; a team's conference is the one it played most
    League matches in. Penalty scores are carried for completeness and never
    rated: a level regulation score is a draw.
    """

    match_id: int
    match_date: date
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    competition: Competition = "league"
    neutral: bool = False
    forfeit: bool = False
    home_in_pool: bool = True
    away_in_pool: bool = True
    kickoff_time: time | None = None
    conference: str | None = None
    home_penalty_score: int | None = None
    away_penalty_score: int | None = None

    @property
    def is_neutral(self) -> bool:
        return self.neutral or self.competition in NEUTRAL_COMPETITIONS


def match_order(m: RatedMatch) -> tuple:
    """Date, then kickoff (untimed last), then id: deterministic for same-day matches."""
    return (m.match_date, m.kickoff_time is None, m.kickoff_time or time.min, m.match_id)


# --- output --------------------------------------------------------------------


@dataclass(frozen=True)
class MatchDelta:
    """One side of one rated match: what it was expected to take and what it moved."""

    match_id: int
    match_date: date
    team_id: int
    opponent_id: int
    rating_before: float
    opponent_before: float
    expected: float
    result: float  # 1 / 0.5 / 0
    k: float
    margin_mult: float
    delta: float


@dataclass(frozen=True)
class TeamRating:
    team_id: int
    rating: float
    start_rating: float
    mp: int  # rated matches
    w: int
    d: int
    l: int
    xconf_mp: int  # rated matches against a team of another conference
    sos: float  # mean opponent rating before each rated match
    island: int
    conference: str | None
    ranked: bool  # mp >= MIN_MATCHES
    provisional: bool  # mp < PROVISIONAL_MATCHES
    low_cross_conference: bool  # xconf_mp < LOW_CROSS_CONFERENCE
    tier: str | None  # national lists only, ranked teams in the main island


@dataclass(frozen=True)
class Publication:
    national: bool
    reason: str | None  # why not national; None when it is
    main_island: int | None
    main_island_share: float | None  # ranked teams in the main island / ranked teams
    cross_conference: dict[str, int]  # main island's conferences -> matches against others


@dataclass(frozen=True)
class PowerRatingResult:
    teams: tuple[TeamRating, ...]  # rating high to low, then team id
    deltas: tuple[MatchDelta, ...]  # two per rated match, in rating order
    matches_counted: int
    matches_excluded: dict[str, int]  # every reason in EXCLUSION_REASONS, 0 when none
    publication: Publication


# --- pure pieces -----------------------------------------------------------------


def expected_score(rating: float, opponent: float, home_advantage: float = 0.0) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(rating - opponent + home_advantage) / SCALE))


def margin_multiplier(goal_difference: int) -> float:
    gd = min(abs(goal_difference), MARGIN_CAP)
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else 1.75


def tier_for(rating: float) -> str | None:
    return next((key for key, _, minimum in TIERS if rating >= minimum), None)


def carry_over(final_ratings: Mapping[int, float], carry: float = ROLLOVER_CARRY) -> dict[int, float]:
    """Next season's starting ratings. Carried teams keep the provisional K."""
    return {t: START_RATING + carry * (r - START_RATING) for t, r in final_ratings.items()}


def select_rated(matches: Iterable[RatedMatch]) -> tuple[list[RatedMatch], dict[str, int]]:
    """(the rated matches in rating order, how many were excluded and why)."""
    excluded = dict.fromkeys(EXCLUSION_REASONS, 0)
    rated = []
    for m in sorted(matches, key=match_order):
        if m.forfeit:
            excluded["forfeit"] += 1
        elif not (m.home_in_pool and m.away_in_pool):
            excluded["out_of_pool_opponent"] += 1
        else:
            rated.append(m)
    return rated, excluded


def team_conferences(matches: Iterable[RatedMatch]) -> dict[int, str]:
    """Each team's conference: the one it played most League matches in (the leaderboards rule)."""
    counts: dict[int, Counter] = defaultdict(Counter)
    for m in matches:
        if m.competition == "league" and m.conference:
            counts[m.home_team_id][m.conference] += 1
            counts[m.away_team_id][m.conference] += 1
    out = {}
    for team_id, divisions in counts.items():
        conference = conference_of(TeamTally(team_id=team_id, name="", divisions=divisions))
        if conference:
            out[team_id] = conference
    return out


def islands(matches: Iterable[RatedMatch]) -> dict[int, int]:
    """Team -> island id. Islands are numbered 1.. by size (largest first), then lowest team id."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for m in matches:
        a, b = find(m.home_team_id), find(m.away_team_id)
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups: dict[int, list[int]] = defaultdict(list)
    for t in list(parent):
        groups[find(t)].append(t)
    ordered = sorted(groups.values(), key=lambda g: (-len(g), min(g)))
    return {t: i for i, group in enumerate(ordered, start=1) for t in group}


def is_cross_conference(m: RatedMatch, conferences: Mapping[int, str]) -> bool:
    home, away = conferences.get(m.home_team_id), conferences.get(m.away_team_id)
    return home is not None and away is not None and home != away


def publication(
    teams: Iterable[TeamRating], rated: Iterable[RatedMatch], conferences: Mapping[int, str]
) -> Publication:
    """National list or conference lists only, by the islands rule."""
    ranked = [t for t in teams if t.ranked]
    if not ranked:
        return Publication(False, "No team has enough rated matches yet.", None, None, {})
    per_island = Counter(t.island for t in ranked)
    main, size = sorted(per_island.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    share = size / len(ranked)
    island_of = {t.team_id: t.island for t in teams}
    in_main = {conferences[t] for t, i in island_of.items() if i == main and t in conferences}
    cross = dict.fromkeys(sorted(in_main), 0)
    for m in rated:
        if island_of.get(m.home_team_id) == main and is_cross_conference(m, conferences):
            for side in (m.home_team_id, m.away_team_id):
                cross[conferences[side]] += 1
    if share < NATIONAL_ISLAND_SHARE:
        reason = f"The largest connected group holds {share:.0%} of ranked teams; a national list needs 90%."
        return Publication(False, reason, main, share, cross)
    thin = [c for c, n in cross.items() if n < NATIONAL_MIN_CROSS_CONFERENCE]
    if not cross or thin:
        reason = (
            f"Conferences with fewer than {NATIONAL_MIN_CROSS_CONFERENCE} matches against other conferences: "
            f"{', '.join(thin) or 'no conference data'}."
        )
        return Publication(False, reason, main, share, cross)
    return Publication(True, None, main, share, cross)


# --- Elo -------------------------------------------------------------------------


@dataclass
class _Running:
    rating: float
    start: float
    mp: int = 0
    w: int = 0
    d: int = 0
    l: int = 0
    xconf: int = 0
    opponent_sum: float = 0.0


def rate(matches: Iterable[RatedMatch], starting_ratings: Mapping[int, float] | None = None) -> PowerRatingResult:
    """Replay one age group's season and rate every team that has a rated match.

    A team with no rated match is absent from `teams`, never a 1500 with 0 matches.
    """
    matches = list(matches)
    starting_ratings = starting_ratings or {}
    rated, excluded = select_rated(matches)
    conferences = team_conferences(matches)
    state: dict[int, _Running] = {}
    deltas: list[MatchDelta] = []

    def team(t: int) -> _Running:
        if t not in state:
            start = float(starting_ratings.get(t, START_RATING))
            state[t] = _Running(rating=start, start=start)
        return state[t]

    for m in rated:
        home, away = team(m.home_team_id), team(m.away_team_id)
        hfa = 0.0 if m.is_neutral else HOME_ADVANTAGE
        e_home = expected_score(home.rating, away.rating, hfa)
        s_home = 1.0 if m.home_score > m.away_score else 0.0 if m.home_score < m.away_score else 0.5
        g = 1.0 if s_home == 0.5 else margin_multiplier(m.home_score - m.away_score)
        cross = is_cross_conference(m, conferences)
        sides = (
            (m.home_team_id, m.away_team_id, home, away, e_home, s_home),
            (m.away_team_id, m.home_team_id, away, home, 1.0 - e_home, 1.0 - s_home),
        )
        moves = []
        for team_id, opponent_id, me, them, e, s in sides:
            k = K * (PROVISIONAL_K_MULT if me.mp < PROVISIONAL_MATCHES else 1.0)
            delta = k * g * (s - e)
            deltas.append(
                MatchDelta(m.match_id, m.match_date, team_id, opponent_id, me.rating, them.rating, e, s, k, g, delta)
            )
            moves.append((me, them.rating, s, delta))
        for me, opponent_before, s, delta in moves:
            me.rating += delta
            me.mp += 1
            me.opponent_sum += opponent_before
            me.xconf += cross
            if s == 1.0:
                me.w += 1
            elif s == 0.5:
                me.d += 1
            else:
                me.l += 1

    island_of = islands(rated)
    untiered = [
        TeamRating(
            team_id=t,
            rating=r.rating,
            start_rating=r.start,
            mp=r.mp,
            w=r.w,
            d=r.d,
            l=r.l,
            xconf_mp=r.xconf,
            sos=r.opponent_sum / r.mp,
            island=island_of[t],
            conference=conferences.get(t),
            ranked=r.mp >= MIN_MATCHES,
            provisional=r.mp < PROVISIONAL_MATCHES,
            low_cross_conference=r.xconf < LOW_CROSS_CONFERENCE,
            tier=None,
        )
        for t, r in state.items()
    ]
    pub = publication(untiered, rated, conferences)
    # Tiers only once the publication state is known.
    teams = sorted((_with_tier(t, pub) for t in untiered), key=lambda t: (-t.rating, t.team_id))
    return PowerRatingResult(
        teams=tuple(teams),
        deltas=tuple(deltas),
        matches_counted=len(rated),
        matches_excluded=excluded,
        publication=pub,
    )


def _with_tier(t: TeamRating, pub: Publication) -> TeamRating:
    if not (pub.national and t.ranked and t.island == pub.main_island):
        return t
    return replace(t, tier=tier_for(t.rating))


# --- Massey audit ----------------------------------------------------------------


@dataclass(frozen=True)
class MasseyResult:
    ratings: dict[int, float]  # goals better than an average team, per match
    home_advantage: float


def massey(matches: Iterable[RatedMatch], *, cap: int = MASSEY_CAP, ridge: float = MASSEY_RIDGE) -> MasseyResult | None:
    """Capped-margin Massey with a home-advantage term and a ridge on team strengths.

    Rates the same matches Elo does (forfeits and out-of-pool excluded). Neutral
    matches carry no home term. None when there is nothing to rate.
    """
    rated, _ = select_rated(matches)
    if not rated:
        return None
    teams = sorted({t for m in rated for t in (m.home_team_id, m.away_team_id)})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    with_home = any(not m.is_neutral for m in rated)
    cols = n + 1 if with_home else n
    x = np.zeros((len(rated), cols))
    y = np.zeros(len(rated))
    for row, m in enumerate(rated):
        x[row, idx[m.home_team_id]] = 1.0
        x[row, idx[m.away_team_id]] = -1.0
        if with_home and not m.is_neutral:
            x[row, n] = 1.0
        y[row] = max(-cap, min(cap, m.home_score - m.away_score))
    reg = ridge * np.eye(cols)
    if with_home:
        reg[n, n] = 0.0
    beta = np.linalg.solve(x.T @ x + reg, x.T @ y)
    return MasseyResult(
        ratings={t: float(beta[idx[t]]) for t in teams},
        home_advantage=float(beta[n]) if with_home else 0.0,
    )


@dataclass(frozen=True)
class RankGap:
    team_id: int
    island: int
    elo_rank: int
    massey_rank: int

    @property
    def gap(self) -> int:
        return abs(self.elo_rank - self.massey_rank)


def _ranks(team_ids: list[int], value: Mapping[int, float]) -> dict[int, int]:
    return {t: i for i, t in enumerate(sorted(team_ids, key=lambda t: (-value[t], t)), start=1)}


def rank_gaps(result: PowerRatingResult, audit: MasseyResult | None, threshold: int = RANK_GAP_FLAG) -> list[RankGap]:
    """Ranked teams whose Elo and Massey places, within their island, differ by more than `threshold`."""
    if audit is None:
        return []
    by_island: dict[int, list[int]] = defaultdict(list)
    for t in result.teams:
        if t.ranked and t.team_id in audit.ratings:
            by_island[t.island].append(t.team_id)
    elo = {t.team_id: t.rating for t in result.teams}
    out = []
    for island, team_ids in sorted(by_island.items()):
        er, mr = _ranks(team_ids, elo), _ranks(team_ids, audit.ratings)
        out.extend(RankGap(t, island, er[t], mr[t]) for t in team_ids if abs(er[t] - mr[t]) > threshold)
    return sorted(out, key=lambda g: (-g.gap, g.team_id))
