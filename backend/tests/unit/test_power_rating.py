"""MT Power Rating engine (SB-1805): Elo, publication rule, Massey audit.

Hand-computed cases first; one regression test replays the 2026-11-26b freeze
and reproduces `elo_backtest.py`'s recommended-config numbers.
"""

import csv
import random
from datetime import date, time, timedelta
from pathlib import Path

import pytest

from mt_tools.power_rating import (
    HOME_ADVANTAGE,
    MIN_MATCHES,
    PROVISIONAL_MATCHES,
    MasseyResult,
    PowerRatingResult,
    Publication,
    RatedMatch,
    TeamRating,
    carry_over,
    expected_score,
    islands,
    margin_multiplier,
    massey,
    match_order,
    rank_gaps,
    rate,
    team_conferences,
    tier_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.backend]

DAY = date(2026, 9, 5)
E_HOME = 1 / (1 + 10 ** (-50 / 400))  # 0.5715: equal teams, the home side's expected score


def match(mid, home, away, hs, as_, *, day=0, **kw) -> RatedMatch:
    return RatedMatch(mid, DAY + timedelta(days=day), home, away, hs, as_, **kw)


def team(result: PowerRatingResult, team_id: int) -> TeamRating:
    return next(t for t in result.teams if t.team_id == team_id)


def deltas(result: PowerRatingResult, team_id: int) -> list[float]:
    return [d.delta for d in result.deltas if d.team_id == team_id]


# --- one match, by hand ------------------------------------------------------------


class TestOneMatch:
    def test_home_win(self):
        r = rate([match(1, 10, 20, 1, 0)])
        # Both new: K = 60. G = 1 for a one-goal win. 60 * (1 - 0.5715) = +25.71.
        assert team(r, 10).rating == pytest.approx(1500 + 60 * (1 - E_HOME))
        assert team(r, 20).rating == pytest.approx(1500 - 60 * (1 - E_HOME))
        assert team(r, 10).rating == pytest.approx(1525.71, abs=0.01)
        assert (team(r, 10).w, team(r, 10).d, team(r, 10).l) == (1, 0, 0)
        assert (team(r, 20).w, team(r, 20).d, team(r, 20).l) == (0, 0, 1)

    def test_draw_costs_the_home_side(self):
        r = rate([match(1, 10, 20, 1, 1)])
        assert team(r, 10).rating == pytest.approx(1500 + 60 * (0.5 - E_HOME))
        assert team(r, 10).rating == pytest.approx(1495.71, abs=0.01)
        assert team(r, 10).d == 1

    def test_away_win_by_two(self):
        r = rate([match(1, 10, 20, 0, 2)])
        # G = 1.5: 60 * 1.5 * (0 - 0.5715) = -51.43
        assert team(r, 10).rating == pytest.approx(1500 - 60 * 1.5 * E_HOME)
        assert team(r, 20).rating == pytest.approx(1500 + 60 * 1.5 * E_HOME)

    def test_home_advantage_is_only_in_the_expected_score(self):
        r = rate([match(1, 10, 20, 1, 0)])
        d = next(d for d in r.deltas if d.team_id == 10)
        assert d.rating_before == d.opponent_before == 1500
        assert d.expected == pytest.approx(expected_score(1500, 1500, HOME_ADVANTAGE))
        away = next(d for d in r.deltas if d.team_id == 20)
        assert away.expected == pytest.approx(1 - E_HOME)

    @pytest.mark.parametrize("competition", ["tournament", "cup"])
    def test_tournaments_and_cups_are_neutral(self, competition):
        r = rate([match(1, 10, 20, 1, 0, competition=competition)])
        assert team(r, 10).rating == pytest.approx(1530)  # 60 * (1 - 0.5)

    def test_neutral_flag_on_a_league_match(self):
        r = rate([match(1, 10, 20, 0, 0, neutral=True)])
        assert team(r, 10).rating == team(r, 20).rating == 1500

    def test_shootout_is_a_regulation_draw(self):
        r = rate([match(1, 10, 20, 2, 2, competition="flex", home_penalty_score=5, away_penalty_score=4)])
        home = team(r, 10)
        assert (home.w, home.d, home.l) == (0, 1, 0)
        assert home.rating == pytest.approx(1500 + 60 * (0.5 - E_HOME))
        assert next(d for d in r.deltas if d.team_id == 10).result == 0.5


class TestMargin:
    @pytest.mark.parametrize(("gd", "g"), [(0, 1.0), (1, 1.0), (-1, 1.0), (2, 1.5), (-2, 1.5), (3, 1.75), (9, 1.75)])
    def test_multiplier(self, gd, g):
        assert margin_multiplier(gd) == g

    def test_winning_by_more_than_three_earns_nothing_extra(self):
        three = rate([match(1, 10, 20, 3, 0)])
        seven = rate([match(1, 10, 20, 7, 0)])
        assert team(three, 10).rating == team(seven, 10).rating
        assert next(d for d in seven.deltas if d.team_id == 10).margin_mult == 1.75


# --- K, zero sum, rollover -----------------------------------------------------------


class TestK:
    def test_provisional_k_for_the_first_eight_then_normal(self):
        # Team 10 plays nine different new opponents at a neutral venue, winning each.
        ms = [match(i, 10, 100 + i, 1, 0, day=i, neutral=True) for i in range(1, 10)]
        r = rate(ms)
        ks = [d.k for d in r.deltas if d.team_id == 10]
        assert ks == [60.0] * PROVISIONAL_MATCHES + [30.0]
        assert all(d.k == 60.0 for d in r.deltas if d.team_id != 10)

    def test_exchange_is_zero_sum_on_equal_k(self):
        rng = random.Random(1805)
        ms = [
            match(i, a, b, rng.randint(0, 4), rng.randint(0, 4), day=i)
            for i, (a, b) in enumerate([(1, 2), (2, 3), (3, 1), (1, 4), (4, 2), (3, 4)], start=1)
        ]
        r = rate(ms)  # every team under 8 matches: K = 60 on both sides throughout
        assert sum(t.rating for t in r.teams) == pytest.approx(1500 * 4)
        for m in ms:
            pair = [d.delta for d in r.deltas if d.match_id == m.match_id]
            assert sum(pair) == pytest.approx(0)

    def test_not_zero_sum_when_one_side_is_provisional(self):
        established = [match(i, 10, 100 + i, 0, 0, day=i, neutral=True) for i in range(1, 9)]
        r = rate([*established, match(99, 10, 200, 1, 0, day=20, neutral=True)])
        last = {d.team_id: d for d in r.deltas if d.match_id == 99}
        assert (last[10].k, last[200].k) == (30.0, 60.0)
        assert last[10].delta == pytest.approx(15)
        assert last[200].delta == pytest.approx(-30)

    def test_rollover_carries_thirty_percent(self):
        assert carry_over({1: 1700.0, 2: 1400.0}) == {1: pytest.approx(1560), 2: pytest.approx(1470)}

    def test_starting_ratings_keep_the_provisional_k(self):
        r = rate([match(1, 10, 20, 1, 0, neutral=True)], starting_ratings={10: 1560.0})
        home = team(r, 10)
        assert home.start_rating == 1560
        d = next(d for d in r.deltas if d.team_id == 10)
        assert d.k == 60.0
        assert home.rating == pytest.approx(1560 + 60 * (1 - expected_score(1560, 1500)))
        assert team(r, 20).start_rating == 1500


# --- what is not rated -----------------------------------------------------------------


class TestExcluded:
    def test_forfeit_and_out_of_pool_are_skipped_and_counted(self):
        r = rate(
            [
                match(1, 10, 20, 1, 0),
                match(2, 10, 30, 3, 0, day=1, forfeit=True),
                match(3, 10, 40, 0, 5, day=2, away_in_pool=False),
                match(4, 50, 10, 0, 1, day=3, home_in_pool=False),
            ]
        )
        assert r.matches_counted == 1
        assert r.matches_excluded == {"forfeit": 1, "out_of_pool_opponent": 2}
        assert team(r, 10).mp == 1
        assert team(r, 10).rating == pytest.approx(1500 + 60 * (1 - E_HOME))
        # Absent, not a 1500 with 0 matches.
        assert {t.team_id for t in r.teams} == {10, 20}

    def test_empty_input_is_empty_not_zeros(self):
        r = rate([])
        assert r.teams == ()
        assert r.deltas == ()
        assert r.matches_counted == 0
        assert r.matches_excluded == {"forfeit": 0, "out_of_pool_opponent": 0}
        assert r.publication.national is False
        assert r.publication.reason
        assert r.publication.main_island is None

    def test_only_excluded_matches_is_empty(self):
        r = rate([match(1, 10, 20, 1, 0, forfeit=True)])
        assert r.teams == ()
        assert r.matches_excluded["forfeit"] == 1


# --- order -------------------------------------------------------------------------


class TestOrder:
    def test_same_day_order_is_by_kickoff_then_id_whatever_the_input_order(self):
        ms = [
            match(5, 10, 20, 2, 0),
            match(3, 20, 30, 1, 1),
            match(9, 30, 10, 0, 1, kickoff_time=time(9, 0)),
            match(1, 10, 30, 0, 0),
        ]
        expected = [9, 1, 3, 5]  # timed first, then untimed by id
        assert [m.match_id for m in sorted(ms, key=match_order)] == expected
        first = rate(ms)
        for seed in range(5):
            shuffled = ms[:]
            random.Random(seed).shuffle(shuffled)
            again = rate(shuffled)
            assert again.teams == first.teams
            assert again.deltas == first.deltas
        assert [d.match_id for d in first.deltas[::2]] == expected

    def test_dates_before_ids(self):
        ms = [match(1, 10, 20, 1, 0, day=1), match(2, 10, 20, 0, 1, day=0)]
        assert [m.match_id for m in sorted(ms, key=match_order)] == [2, 1]


# --- per-team fields -----------------------------------------------------------------


def round_robin(teams, *, start_id=1, start_day=0, conference=None, rounds=1, rng=None):
    """Every pair once per round, home and away alternating, scores from `rng` (default: home 1-0)."""
    out = []
    mid, day = start_id, start_day
    for r in range(rounds):
        for i, a in enumerate(teams):
            for b in teams[i + 1 :]:
                home, away = (a, b) if r % 2 == 0 else (b, a)
                hs, as_ = (rng.randint(0, 3), rng.randint(0, 3)) if rng else (1, 0)
                out.append(match(mid, home, away, hs, as_, day=day, conference=conference))
                mid += 1
                day += 1
    return out


class TestTeamFields:
    def test_strength_of_schedule_is_mean_opponent_rating_before(self):
        # 20 beats 30 first, so 10 then meets a stronger 20 and a weaker 30.
        r = rate([match(1, 20, 30, 3, 0), match(2, 10, 20, 0, 0, day=1), match(3, 10, 30, 0, 0, day=2)])
        before_20 = next(d.rating_before for d in r.deltas if d.match_id == 2 and d.team_id == 20)
        before_30 = next(d.rating_before for d in r.deltas if d.match_id == 3 and d.team_id == 30)
        assert before_20 == pytest.approx(1500 + 60 * 1.75 * (1 - E_HOME))
        assert team(r, 10).sos == pytest.approx((before_20 + before_30) / 2)

    def test_delta_log_has_two_rows_per_match(self):
        r = rate([match(1, 10, 20, 2, 0)])
        assert len(r.deltas) == 2
        home = next(d for d in r.deltas if d.team_id == 10)
        assert (home.match_id, home.opponent_id, home.result, home.margin_mult) == (1, 20, 1.0, 1.5)
        assert home.delta == pytest.approx(60 * 1.5 * (1 - E_HOME))

    def test_conference_is_where_most_league_matches_were(self):
        ms = [
            match(1, 10, 20, 1, 0, conference="Northeast"),
            match(2, 10, 21, 1, 0, day=1, conference="Northeast"),
            match(3, 10, 30, 1, 0, day=2, conference="Florida"),
            match(4, 10, 31, 1, 0, day=3, competition="flex", conference="Florida"),
        ]
        conf = team_conferences(ms)
        assert conf[10] == "Northeast"
        assert conf[30] == "Florida"
        assert 31 not in conf  # Flex alone gives no conference
        r = rate(ms)
        assert team(r, 31).conference is None
        # 10 (Northeast) v 30 (Florida) is the one cross-conference match; v 31 has no conference.
        assert team(r, 10).xconf_mp == 1
        assert team(r, 30).xconf_mp == 1

    def test_conference_tie_is_alphabetical(self):
        ms = [match(1, 10, 20, 1, 0, conference="Texas"), match(2, 10, 30, 1, 0, day=1, conference="Florida")]
        assert team_conferences(ms)[10] == "Florida"


class TestBadges:
    def _played(self, n, xconf=0):
        """Team 10 plays n matches, the first `xconf` of them against another conference."""
        ms = [match(1000 + i, 900 + i, 901 + i, 0, 0, day=0, conference="B") for i in range(0, 4, 2)]
        ms += [match(2000, 10, 950, 0, 0, conference="A")]  # gives 10 conference A
        for i in range(n - 1):
            opp = 900 if i < xconf else 960 + i
            ms.append(match(i + 1, 10, opp, 0, 0, day=i + 1, competition="flex"))
        return team(rate(ms), 10)

    @pytest.mark.parametrize(
        ("mp", "ranked", "provisional"), [(5, False, True), (6, True, True), (7, True, True), (8, True, False)]
    )
    def test_ranked_and_provisional(self, mp, ranked, provisional):
        t = self._played(mp)
        assert t.mp == mp
        assert (t.ranked, t.provisional) == (ranked, provisional)
        assert MIN_MATCHES == 6

    @pytest.mark.parametrize(("xconf", "low"), [(0, True), (2, True), (3, False)])
    def test_low_cross_conference(self, xconf, low):
        t = self._played(8, xconf)
        assert t.xconf_mp == xconf
        assert t.low_cross_conference is low


class TestTiers:
    @pytest.mark.parametrize(
        ("rating", "tier"),
        [
            (1800.0, "elite"),
            (1700.0, "elite"),
            (1699.99, "contender"),
            (1600.0, "contender"),
            (1599.99, "above_average"),
            (1500.0, "above_average"),
            (1499.99, None),
            (1200.0, None),
        ],
    )
    def test_boundaries(self, rating, tier):
        assert tier_for(rating) == tier


# --- islands and publication -------------------------------------------------------------


def two_conferences(cross_matches: int):
    """Conference A (1-4) and B (11-14), a double round robin each, plus `cross_matches` A v B matches."""
    rng = random.Random(7)
    ms = round_robin([1, 2, 3, 4], conference="A", rounds=2, rng=rng)
    ms += round_robin([11, 12, 13, 14], start_id=100, conference="B", rounds=2, rng=rng)
    for i in range(cross_matches):
        ms.append(match(200 + i, 1 + i % 4, 11 + i % 4, 2, 0, day=50 + i, competition="flex"))
    return ms


class TestPublication:
    def test_islands_are_numbered_largest_first(self):
        ms = [match(1, 5, 6, 0, 0), match(2, 1, 2, 0, 0), match(3, 2, 3, 0, 0)]
        assert islands(ms) == {1: 1, 2: 1, 3: 1, 5: 2, 6: 2}

    def test_isolated_conferences_are_conference_lists_only(self):
        r = rate(two_conferences(0))
        assert {t.island for t in r.teams} == {1, 2}
        assert all(t.ranked for t in r.teams)
        assert r.publication.national is False
        assert r.publication.main_island_share == pytest.approx(0.5)
        assert "50%" in r.publication.reason
        assert all(t.tier is None for t in r.teams)

    def test_connected_conferences_are_national_with_tiers(self):
        r = rate(two_conferences(6))
        assert {t.island for t in r.teams} == {1}
        assert r.publication == Publication(True, None, 1, 1.0, {"A": 6, "B": 6})
        assert all(t.tier == tier_for(t.rating) for t in r.teams)
        assert any(t.tier is not None for t in r.teams)

    def test_one_island_but_a_thin_conference_is_not_national(self):
        r = rate(two_conferences(4))
        assert r.publication.main_island_share == 1.0
        assert r.publication.national is False
        assert r.publication.cross_conference == {"A": 4, "B": 4}
        assert "A, B" in r.publication.reason

    def test_unranked_teams_do_not_count_towards_the_share_and_get_no_tier(self):
        ms = [*two_conferences(6), match(300, 50, 51, 1, 0, day=90)]  # a 2-team island, 1 match each
        r = rate(ms)
        assert r.publication.national is True
        assert team(r, 50).island == 2
        assert team(r, 50).ranked is False
        assert team(r, 50).tier is None


# --- Massey audit ---------------------------------------------------------------------


class TestMassey:
    def test_tiny_consistent_set(self):
        # Neutral: A beat B by 1, B beat C by 1, A beat C by 2. X'X = 3I - J and X'y = (3, 0, -3),
        # so with ridge 1 the solution is X'y / 4.
        ms = [
            match(1, 1, 2, 1, 0, neutral=True),
            match(2, 2, 3, 1, 0, neutral=True),
            match(3, 1, 3, 2, 0, neutral=True),
        ]
        m = massey(ms)
        assert m.ratings == {1: pytest.approx(0.75), 2: pytest.approx(0.0), 3: pytest.approx(-0.75)}
        assert m.home_advantage == 0.0

    def test_home_advantage_term(self):
        m = massey([match(1, 1, 2, 1, 0), match(2, 2, 1, 1, 0, day=1)])
        assert m.home_advantage == pytest.approx(1.0)
        assert m.ratings == {1: pytest.approx(0.0), 2: pytest.approx(0.0)}

    def test_margin_is_capped_at_four(self):
        assert (
            massey([match(1, 1, 2, 9, 0, neutral=True)]).ratings == massey([match(1, 1, 2, 4, 0, neutral=True)]).ratings
        )

    def test_excludes_what_elo_excludes_and_empty_is_none(self):
        assert massey([]) is None
        assert massey([match(1, 1, 2, 1, 0, forfeit=True)]) is None
        m = massey([match(1, 1, 2, 1, 0, neutral=True), match(2, 1, 3, 9, 0, away_in_pool=False)])
        assert set(m.ratings) == {1, 2}


def _team(team_id, rating, *, island=1, ranked=True):
    return TeamRating(
        team_id, rating, 1500.0, 10 if ranked else 2, 0, 0, 0, 0, 1500.0, island, None, ranked, False, True, None
    )


class TestRankGaps:
    def _result(self, teams):
        return PowerRatingResult(tuple(teams), (), 0, {}, Publication(False, "x", 1, 1.0, {}))

    def test_flags_gaps_above_threshold_within_island(self):
        teams = [_team(t, 1600.0 - t) for t in range(1, 41)]  # Elo order 1..40
        audit = MasseyResult({t: float(t) for t in range(1, 41)}, 0.0)  # Massey order 40..1
        gaps = rank_gaps(self._result(teams), audit)
        # |rank_elo - rank_massey| = |41 - 2t|, above 30 for t <= 5 and t >= 36.
        assert sorted(g.team_id for g in gaps) == [1, 2, 3, 4, 5, 36, 37, 38, 39, 40]
        assert gaps[0].gap == 39
        assert {(g.elo_rank, g.massey_rank) for g in gaps if g.team_id == 1} == {(1, 40)}

    def test_exactly_the_threshold_is_not_flagged(self):
        teams = [_team(t, 1600.0 - t) for t in range(1, 4)]
        audit = MasseyResult({1: 0.0, 2: 1.0, 3: 2.0}, 0.0)
        assert [g.team_id for g in rank_gaps(self._result(teams), audit, threshold=2)] == []
        assert {g.team_id for g in rank_gaps(self._result(teams), audit, threshold=1)} == {1, 3}

    def test_unranked_teams_and_other_islands_are_ranked_apart(self):
        teams = [_team(1, 1600.0), _team(2, 1500.0), _team(3, 1700.0, island=2), _team(4, 1800.0, ranked=False)]
        audit = MasseyResult({1: 0.0, 2: 1.0, 3: 5.0, 4: -9.0}, 0.0)
        gaps = rank_gaps(self._result(teams), audit, threshold=0)
        assert {(g.team_id, g.elo_rank, g.massey_rank) for g in gaps} == {(1, 1, 2), (2, 2, 1)}

    def test_no_audit_no_gaps(self):
        assert rank_gaps(self._result([_team(1, 1600.0)]), None) == []


# --- regression: the 2026-11-26b freeze --------------------------------------------------

FREEZE = Path.home() / ".local/share/mt-ranking-backtest/2026-11-26b/results_2026-11-26b.csv"


@pytest.mark.skipif(
    not FREEZE.exists(),
    reason=f"backtest freeze not on this machine ({FREEZE}); it lives outside the repo (SB-1784)",
)
def test_reproduces_elo_backtest_recommended_config():
    """elo_backtest.py RECOMMENDED (K30, flex 1.0, cap 3, HFA 50, prov) on the 26b freeze.

    The backtest rated every match, out-of-pool opponents included, so the
    first checks mark every side in pool; the last applies the production rule.
    """
    with FREEZE.open() as fh:
        rows = list(csv.DictReader(fh))

    def load(pool=None):
        return {
            age: [
                RatedMatch(
                    int(r["match_id"]),
                    date.fromisoformat(r["match_date"]),
                    int(r["home_team_id"]),
                    int(r["away_team_id"]),
                    int(r["home_score"]),
                    int(r["away_score"]),
                    competition=r["match_type"].lower(),
                    conference=r["division"] if r["league"] == "Homegrown" and r["match_type"] == "League" else None,
                    home_in_pool=pool is None or int(r["home_team_id"]) in pool[age],
                    away_in_pool=pool is None or int(r["away_team_id"]) in pool[age],
                )
                for r in rows
                if r["age_group"] == age
            ]
            for age in ("U15", "U16", "U17", "U19")
        }

    per_age = load()

    def home_diff(ratings, m):
        return ratings.get(m.home_team_id, 1500.0) - ratings.get(m.away_team_id, 1500.0) + HOME_ADVANTAGE

    # Split test: rate to Oct 31, predict decided November matches with no updates.
    cutoff = date(2026, 10, 31)
    split = {}
    for age, ms in per_age.items():
        ratings = {t.team_id: t.rating for t in rate(m for m in ms if m.match_date <= cutoff).teams}
        test = [m for m in ms if m.match_date > cutoff and m.home_score != m.away_score]
        split[age] = (sum((home_diff(ratings, m) > 0) == (m.home_score > m.away_score) for m in test), len(test))
    assert split == {"U15": (137, 183), "U16": (162, 217), "U17": (165, 223), "U19": (157, 222)}
    assert sum(h for h, _ in split.values()) == 621  # of 845 = 73.5%

    # Walk-forward: each match day predicted from ratings built on earlier days only.
    oct_sq, nov_sq, nov_hits = [], [], []
    for ms in per_age.values():
        for day in sorted({m.match_date for m in ms}):
            ratings = {t.team_id: t.rating for t in rate(m for m in ms if m.match_date < day).teams}
            for m in (m for m in ms if m.match_date == day):
                s = 1.0 if m.home_score > m.away_score else 0.0 if m.home_score < m.away_score else 0.5
                e = 1 / (1 + 10 ** (-home_diff(ratings, m) / 400))
                if date(2026, 10, 1) <= day < date(2026, 11, 1):
                    oct_sq.append((s - e) ** 2)
                elif day >= date(2026, 11, 1):
                    nov_sq.append((s - e) ** 2)
                    if s != 0.5:
                        nov_hits.append((e > 0.5) == (s == 1.0))
    assert round(sum(oct_sq) / len(oct_sq), 4) == 0.1678
    assert round(sum(nov_sq) / len(nov_sq), 4) == 0.1513
    assert len(nov_hits) == 845
    assert round(100 * sum(nov_hits) / len(nov_hits), 1) == 73.4

    # At the freeze: ranked (6+ matches) teams and their rating range, per age.
    freeze = {}
    for age, ms in per_age.items():
        ranked = [t.rating for t in rate(ms).teams if t.ranked]
        freeze[age] = (len(ranked), round(min(ranked)), round(max(ranked)))
    assert freeze == {
        "U15": (129, 1223, 1766),
        "U16": (146, 1203, 1778),
        "U17": (148, 1198, 1754),
        "U19": (147, 1180, 1759),
    }

    # Production rule: out-of-pool opponents excluded (96 matches), islands unchanged.
    pool = {
        age: {
            int(r[side])
            for r in rows
            if r["age_group"] == age and r["league"] == "Homegrown"
            for side in ("home_team_id", "away_team_id")
        }
        for age in per_age
    }
    results = {age: rate(ms) for age, ms in load(pool).items()}
    assert sum(r.matches_excluded["out_of_pool_opponent"] for r in results.values()) == 96
    sizes = {}
    for age, r in results.items():
        count: dict[int, int] = {}
        for t in r.teams:
            count[t.island] = count.get(t.island, 0) + 1
        sizes[age] = sorted(count.values(), reverse=True)
    assert sizes == {
        "U15": [21, 20, 17, 16, 14, 14, 13, 9],
        "U16": [107, 40],
        "U17": [147],
        "U19": [146],
    }
    assert {age: r.publication.national for age, r in results.items()} == {
        "U15": False,
        "U16": False,
        "U17": True,
        "U19": True,
    }
    assert min(results["U17"].publication.cross_conference.values()) == 8  # the thinnest, Southwest
