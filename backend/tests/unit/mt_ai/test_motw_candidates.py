"""Match of the Week candidate scoring (SB-1550).

The world here is MT's default: scraped fixtures and results, no rosters, no
logged goals. Nothing in a candidate may depend on user data.
"""

from datetime import date

import pytest
from motw_fakes import NORTHEAST, NOW, TURNPIKE, U16, default_matches, deps, match, played
from structlog.testing import capture_logs

from mt_tools.motw_candidates import (
    FEATURED_PENALTY,
    POOL,
    PRO_PATHWAY_POOL,
    REMATCH,
    REMATCH_CLOSE,
    Pool,
    TeamStanding,
    _percentiles,
    form_score,
    rematch_score,
    score_fixture,
    stakes_score,
    standings_from_rows,
    streak_text,
    suggest_motw_candidates,
    team_strengths,
    week_bounds,
)

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 7)


def no_picks(_week: str):
    return None


def run(week=None, picks=no_picks, **kw):
    return suggest_motw_candidates(kw.pop("d", None) or deps(), week, picks=picks, now=NOW, **kw)


def by_id(result):
    return {c.match_id: c for c in result.candidates}


# --- pure functions -------------------------------------------------------------


class TestPure:
    def test_percentiles_share_ties(self):
        assert _percentiles({1: 3.0, 2: 1.0, 3: 1.0}) == {1: 1.0, 2: 0.25, 3: 0.25}
        assert _percentiles({1: 2.0}) == {1: 0.5}

    def test_cross_age_normalization(self):
        """Two tables with the same order but different scales give the same strengths."""
        u15 = standings_from_rows(
            [
                {"team_id": 1, "played": 4, "points": 12, "goals_for": 12, "goals_against": 1},
                {"team_id": 2, "played": 4, "points": 6, "goals_for": 5, "goals_against": 5},
                {"team_id": 3, "played": 4, "points": 0, "goals_for": 0, "goals_against": 11},
            ]
        )
        u19 = standings_from_rows(
            [
                {"team_id": 1, "played": 4, "points": 8, "goals_for": 5, "goals_against": 2},
                {"team_id": 2, "played": 4, "points": 5, "goals_for": 4, "goals_against": 4},
                {"team_id": 3, "played": 4, "points": 3, "goals_for": 2, "goals_against": 5},
            ]
        )
        assert team_strengths(u15) == team_strengths(u19)

    def test_low_sample_is_damped_and_flagged(self):
        table = standings_from_rows(
            [
                {"team_id": 1, "played": 1, "points": 3, "goals_for": 3, "goals_against": 0},
                {"team_id": 2, "played": 5, "points": 0, "goals_for": 0, "goals_against": 9},
            ]
        )
        strengths = team_strengths(table)
        assert strengths[1] == (pytest.approx(0.5 + 0.5 / 3), True)
        assert strengths[2] == (0.0, False)

    def test_team_without_games_is_neutral_not_zero(self):
        table = {9: TeamStanding(9, 1, 0, 0, 0, 0, 0, 0, 0)}
        assert team_strengths(table)[9] == (0.5, True)

    def test_form_score_weights_newest_most(self):
        assert form_score(["W", "L"]) == pytest.approx(5 / 9)
        assert form_score(["L", "W"]) == pytest.approx(4 / 9)
        assert form_score([]) is None
        assert form_score(["W"] * 8) == 1.0

    def test_stakes(self):
        a = TeamStanding(1, 1, 3, 7, 2, 1, 0, 0, 0)
        b = TeamStanding(2, 2, 3, 5, 1, 2, 0, 0, 0)
        c = TeamStanding(3, 6, 3, 1, 0, 1, 2, 0, 0)
        table = {1: a, 2: b, 3: c}
        assert stakes_score(a, b, 6, [1], table) == (1.0, ["adjacent", "qualifying_line", "top_of_table"])
        assert stakes_score(a, c, 6, [], table) == (0.0, [])
        assert stakes_score(None, b, 6, [1], table) == (0.0, [])

    def test_rematch_score_follows_the_latest_meeting(self):
        close = {"match_date": "2026-10-01", "home_score": 2, "away_score": 1}
        draw = {"match_date": "2026-10-01", "home_score": 1, "away_score": 1}
        rout = {"match_date": "2026-10-20", "home_score": 5, "away_score": 0}
        assert rematch_score([]) == 0.0
        assert rematch_score([close]) == rematch_score([draw]) == REMATCH_CLOSE
        assert rematch_score([rout]) == REMATCH
        assert rematch_score([close, rout]) == REMATCH

    def test_a_rematch_counts_without_table_rows(self):
        assert stakes_score(None, None, 0, [], {}, rematch=REMATCH) == (REMATCH, ["rematch"])

    def test_stakes_takes_the_highest_component(self):
        a = TeamStanding(1, 1, 3, 7, 2, 1, 0, 0, 0)
        b = TeamStanding(2, 2, 3, 5, 1, 2, 0, 0, 0)
        table = {1: a, 2: b}
        assert stakes_score(a, b, 6, [], table, rematch=REMATCH) == (1.0, ["adjacent", "rematch", "top_of_table"])

    def test_featured_penalty(self):
        plain = score_fixture(0.8, 0.8, 1.0, 1.0, 1.0, featured=False)
        featured = score_fixture(0.8, 0.8, 1.0, 1.0, 1.0, featured=True)
        assert featured.total == pytest.approx(plain.total * FEATURED_PENALTY, abs=1e-4)

    def test_missing_form_is_neutral(self):
        assert score_fixture(0.5, 0.5, 0.0, None, None, featured=False).form == 0.5

    @pytest.mark.parametrize(
        ("results", "text"),
        [
            (["W", "W", "W"], "won all 3"),
            (["W", "W", "W", "L"], "won 3 League/Flex games in a row"),
            (["D", "W", "D", "L"], "unbeaten in 3"),
            (["L", "L", "L", "W"], "lost 3 in a row"),
            (["W", "L", "W"], None),
        ],
    )
    def test_streaks(self, results, text):
        out = streak_text("Team", results)
        assert (out is None) if text is None else (text in out)

    def test_week_bounds(self):
        assert week_bounds(None, TODAY) == (date(2026, 11, 2), date(2026, 11, 8))
        assert week_bounds("2026-11-14", TODAY) == (date(2026, 11, 9), date(2026, 11, 15))


# --- the tool --------------------------------------------------------------------


class TestRematch:
    """Teams 4 and 5 (and 4 and 6) have not met in the default world."""

    def candidate(self, fixture, *extra):
        matches = [*default_matches(), *extra, fixture]
        return by_id(run(d=deps(matches), limit=10))[fixture["id"]]

    def fact(self, candidate):
        return next(f for f in candidate.facts if f.id.endswith(":h2h")).text

    def test_a_decided_flex_game_then_a_league_rematch(self):
        """The Bayside vs IFA shape: a heavy Flex result, then a League game."""
        c = self.candidate(
            match(4, 6, "2026-11-08", NORTHEAST, mid=601),
            played(4, 6, "2026-10-24", TURNPIKE, 5, 0),
        )
        assert "rematch" in c.flags
        assert c.score.stakes >= REMATCH
        assert self.fact(c) == "2nd meeting this season. They met on Oct 24 (Flex): Team 4 5-0 Team 6."

    def test_a_close_earlier_game_is_the_highest_stakes(self):
        c = self.candidate(
            match(4, 6, "2026-11-08", NORTHEAST, mid=602),
            played(4, 6, "2026-10-24", TURNPIKE, 2, 1),
        )
        assert c.score.stakes == REMATCH_CLOSE

    @pytest.mark.parametrize("status", ["scheduled", "cancelled"])
    def test_the_earlier_game_must_have_been_played(self, status):
        c = self.candidate(
            match(4, 5, "2026-11-08", TURNPIKE, mid=603),
            match(4, 5, "2026-10-24", TURNPIKE, status=status),
        )
        assert "rematch" not in c.flags

    def test_a_friendly_is_mentioned_but_is_not_a_rematch(self):
        c = self.candidate(
            match(4, 5, "2026-11-08", TURNPIKE, mid=604),
            played(4, 5, "2026-08-20", TURNPIKE, 1, 1, mtype="Friendly"),
        )
        assert "rematch" not in c.flags
        assert self.fact(c) == "They met on Aug 20 (Friendly): Team 4 1-1 Team 5."

    def test_another_age_group_is_not_a_rematch(self):
        c = self.candidate(
            match(4, 5, "2026-11-08", TURNPIKE, mid=605),
            played(4, 5, "2026-10-01", NORTHEAST, 1, 0, age=U16),
        )
        assert "rematch" not in c.flags


class TestSuggest:
    def test_logs_every_eligible_fixtures_score_not_only_those_returned(self):
        with capture_logs() as logs:
            result = run(limit=1)
        [line] = [e for e in logs if e["event"] == "motw_candidates_scored"]
        assert len(result.candidates) == 1
        assert (line["eligible"], line["returned"]) == (3, 1)
        assert len(line["candidates"]) == 3
        top = line["candidates"][0]
        assert top["match_id"] == result.candidates[0].match_id
        assert top["total"] == result.candidates[0].score.total
        assert {"quality", "closeness", "stakes", "form", "penalty", "flags"} <= set(top)

    def test_ranks_the_top_of_table_clash_first(self):
        result = run()
        assert result.error is None
        assert result.week_start == date(2026, 11, 2)
        assert result.candidates[0].match_id == 501

    def test_only_eligible_fixtures(self):
        ids = set(by_id(run()))
        assert 504 not in ids  # in the week but before today
        assert 505 not in ids  # cancelled
        assert 506 not in ids  # another week
        assert {501, 502, 503} <= ids
        assert 507 not in ids  # Pro Player Pathway has its own pool

    def test_pool_is_northeast_league_and_three_flex_conferences(self):
        assert POOL.conferences == (
            ("Homegrown", "Northeast"),
            ("Flex", "Empire"),
            ("Flex", "New England"),
            ("Flex", "Turnpike"),
        )
        assert PRO_PATHWAY_POOL.conferences == (("Homegrown", "Northeast (Pro Player Pathway)"),)

    def test_pro_pathway_pool_ranks_only_its_own_fixtures(self):
        assert set(by_id(run(pool=PRO_PATHWAY_POOL))) == {507}

    def test_coverage_states_the_denominator(self):
        cov = run().coverage
        assert cov.divisions == 4
        assert cov.fixtures_in_week == 5  # 501-505
        assert cov.eligible == 3
        assert cov.rules_season == "2026-27"

    def test_flex_fixture_carries_flex_rules(self):
        top = by_id(run())[501]
        assert "qualifying_line" in top.flags
        rules = {r.id: r.confirmed for r in top.rules}
        assert rules == {"hg-flex-conference-bye-race": True, "hg-flex-conference-winner-berth": False}
        inferred = next(f for f in top.facts if f.rule_id == "hg-flex-conference-winner-berth")
        assert inferred.confirmed is False and inferred.text.startswith("Unconfirmed: ")

    def test_league_fixture_has_no_qualifying_line(self):
        """No source ties a Northeast league finish to a Cup place."""
        ne = by_id(run())[503]
        assert "qualifying_line" not in ne.flags
        assert [r.id for r in ne.rules] == ["hg-league-play"]

    def test_fact_ids_are_unique_and_scoped_to_the_match(self):
        for c in run().candidates:
            ids = [f.id for f in c.facts]
            assert len(ids) == len(set(ids))
            assert all(i.startswith(f"{c.match_id}:") for i in ids)

    def test_facts_from_scraped_data_only(self):
        top = by_id(run())[501]
        ids = {f.id.split(":", 1)[1] for f in top.facts}
        assert {"pos:home", "pos:away", "gap", "h2h", "rate:home", "rate:away"} <= ids
        assert not any("goal" in f.text.lower() and "scorer" in f.text.lower() for f in top.facts)

    def test_history_is_scoped_to_the_age_group(self):
        """Team 1 lost all its U16 games; its U15 form is all wins and a draw."""
        home = by_id(run())[501].home
        assert home.id == 1
        assert home.form > 0.7
        streaks = [f.text for f in by_id(run())[501].facts if f.id.endswith("streak:home")]
        assert streaks and "unbeaten" in streaks[0]

    def test_teams_with_no_games_are_low_sample_not_zero(self):
        ppp = by_id(run(pool=PRO_PATHWAY_POOL))[507]
        assert "low_sample" in ppp.flags
        assert ppp.home.position is None and ppp.home.points is None
        assert ppp.home.strength == 0.5 and ppp.home.form is None
        assert not [f for f in ppp.facts if f.kind == "standings"]

    def test_empty_week(self):
        result = run("2026-12-21")
        assert result.error is None
        assert result.candidates == []
        assert "No pool fixtures" in result.reason
        assert result.coverage.fixtures_in_week == 0

    def test_week_with_nothing_left_to_play(self):
        result = run("2026-10-31")
        assert result.candidates == []
        assert "still to be played" in result.reason

    def test_already_picked_week_still_lists_candidates(self):
        def picks(week):
            if week == "2026-11-02":
                return {"match": {"id": 503, "home_team_id": 5, "away_team_id": 6}, "blurb": "b", "reasons": []}
            return None

        result = run(picks=picks)
        assert result.current_pick.match_id == 503
        assert result.current_pick.has_reasons is False
        assert result.candidates

    def test_recently_featured_teams_are_penalised(self):
        def picks(week):
            if week == "2026-10-26":
                return {"match": {"id": 1, "home_team_id": 1, "away_team_id": 9}}
            return None

        plain = by_id(run())[501]
        result = by_id(run(picks=picks))[501]
        assert "recently_featured" in result.flags
        assert result.score.penalty == FEATURED_PENALTY
        assert result.score.total < plain.score.total

    def test_limit(self):
        assert len(run(limit=2).candidates) == 2
        assert run(limit=0).error.kind == "invalid_args"

    def test_bad_week(self):
        assert run("next tuesday").error.kind == "invalid_args"

    def test_unknown_pool_division_fails_loudly(self):
        pool = Pool(
            age_groups=POOL.age_groups,
            match_types=POOL.match_types,
            conferences=(*POOL.conferences, ("Flex", "Atlantis")),
        )
        result = run(pool=pool)
        assert result.error.kind == "unavailable"
        assert "Flex / Atlantis" in result.error.message
        assert result.candidates is None

    def test_failed_read_is_unavailable_not_empty(self):
        result = run(d=deps(fail=True))
        assert result.error.kind == "unavailable"
        assert result.candidates is None

    def test_test_content_is_never_requested(self):
        d = deps()
        calls = []
        original = d.matches.get_all_matches

        def spy(**kw):
            calls.append(kw["include_test"])
            return original(**kw)

        d.matches.get_all_matches = spy
        run(d=d)
        assert calls and not any(calls)
