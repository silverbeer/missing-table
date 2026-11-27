"""Team dossier (SB-1780): a team inside its own conference tables, at one age group.

The default fixture is MT's normal team: scraped results and nothing else.
"""

import pytest
from dossier_fakes import (
    HG_ONLY,
    MIXED,
    OTHER_ONLY,
    PRO_A,
    PRO_B,
    REAL,
    SHOWCASE,
    STRONG_A,
    STRONG_B,
    TEST_TEAM,
    TESTER,
    UNPLAYED,
    dossier_deps,
    dossier_matches,
    off_table,
    ordering_matches,
)
from motw_fakes import EMPIRE, NORTHEAST, NOW, TURNPIKE, U15, U16, match, played

import mt_tools.team_dossier as dossier_module
from mt_tools.team_dossier import detect_playing_up, get_team_dossier, is_top_third

pytestmark = [pytest.mark.unit, pytest.mark.backend]

CONFERENCE_LABELS = ("Homegrown Northeast", "Flex Turnpike", "Flex Empire", "Flex New England")


def dossier(team_id, age_group_id=U15, *, deps=None, viewer=REAL, **kw):
    return get_team_dossier(deps or dossier_deps(), team_id, age_group_id, viewer=viewer, now=NOW, **kw)


def line(result, division_id):
    return next(c for c in result.conferences if c.division.id == division_id)


class TestConferences:
    def test_homegrown_and_flex_are_separate_lines(self):
        r = dossier(1)
        assert r.error is None
        assert [(c.kind, c.competition, c.division.name) for c in r.conferences] == [
            ("league", "League", "Northeast"),
            ("flex", "Flex", "Turnpike"),
        ]
        hg, flex = line(r, NORTHEAST), line(r, TURNPIKE)
        assert (hg.position, hg.table_size, hg.played) == (1, 6, 3)
        assert (hg.wins, hg.draws, hg.losses, hg.gf, hg.ga, hg.gd) == (2, 1, 0, 6, 2, 4)
        assert hg.ppg == 2.33 and hg.gf_per_game == 2.0 and hg.ga_per_game == 0.67
        assert hg.clean_sheets == 2
        assert (flex.position, flex.table_size, flex.played) == (1, 4, 3)
        assert flex.strength_percentile == 100

    def test_positions_come_from_get_standings(self):
        d = dossier_deps()
        dossier(1, deps=d)
        assert (NORTHEAST, U15, "League") in d.matches.standings_calls
        assert (TURNPIKE, U15, "Flex") in d.matches.standings_calls

    def test_homegrown_only(self):
        r = dossier(HG_ONLY)
        assert [c.kind for c in r.conferences] == ["league"]
        assert "no_conference" not in r.flags

    def test_a_registered_team_with_no_games_is_an_answer_of_nulls(self):
        r = dossier(UNPLAYED)
        assert r.error is None
        assert r.flags == ["no_results"]
        assert r.totals is None
        assert r.key_wins == [] and r.form == []
        (c,) = r.conferences
        assert c.no_results
        for field in ("position", "wins", "draws", "losses", "gf", "ga", "gd", "ppg", "clean_sheets"):
            assert getattr(c, field) is None, field
        assert c.strength_percentile is None
        assert [f.id for f in r.facts] == [f"t{UNPLAYED}:a{U15}:flex:204:no_results"]

    def test_one_empty_table_does_not_blank_the_other(self):
        r = dossier(4)
        assert line(r, NORTHEAST).no_results and line(r, NORTHEAST).position is None
        assert line(r, TURNPIKE).position == 4
        assert line(r, TURNPIKE).clean_sheets == 0  # played and conceded every time: a real 0
        assert r.totals.played == 3

    def test_low_sample_at_two_games(self):
        r = dossier(HG_ONLY)
        c = line(r, NORTHEAST)
        assert c.played == 2 and c.low_sample
        assert "low_sample" in r.flags
        assert "small sample" in next(f.text for f in r.facts if f.id.endswith(":pos"))

    def test_a_registration_outside_homegrown_academy_flex_is_skipped(self):
        d = dossier_deps()
        r = dossier(MIXED, deps=d)
        assert [c.division.id for c in r.conferences] == [NORTHEAST]
        assert all(call[0] != SHOWCASE for call in d.matches.standings_calls)
        assert "no_conference" in dossier(OTHER_ONLY).flags

    def test_no_registration_at_the_age_is_no_conference(self):
        r = dossier(3, U16)
        assert r.error is None
        assert r.conferences == []
        assert set(r.flags) == {"no_conference", "no_results"}


class TestKeyWins:
    def test_top_third_wins_strongest_first(self):
        r = dossier(4, deps=dossier_deps(ordering_matches()))
        assert [(w.match_id, w.opponent.id, w.kind) for w in r.key_wins] == [
            (701, STRONG_A, "top_third"),  # the leader, though the older win
            (702, STRONG_B, "top_third"),
        ]
        assert r.key_wins[0].opponent_position == 1 and r.key_wins[0].opponent_table_size == 6
        assert r.key_wins[0].score == "1-0"

    def test_a_win_outside_the_top_third_is_not_key(self):
        r = dossier(1)
        assert [w.opponent.id for w in r.key_wins] == [6]  # 2nd of 6; Team 5 is 4th

    def test_a_non_pro_beating_a_pro_academy_is_an_upset(self):
        r = dossier(HG_ONLY)
        (w,) = r.key_wins
        assert (w.match_id, w.opponent.id, w.kind, w.score) == (610, PRO_A, "pro_academy_upset", "3-2")
        assert w.opponent_pro_academy and not w.top_third
        assert w.competition == "Tournament"
        assert "not a pro academy" in next(f.text for f in r.facts if f.id == w.fact_id)

    def test_a_pro_academy_beating_another_is_not_an_upset(self):
        r = dossier(PRO_B)
        (w,) = r.key_wins
        assert (w.opponent.id, w.kind) == (PRO_A, "pro_academy")
        assert r.team.pro_academy

    def test_an_opponent_with_no_table_is_not_a_top_third_win(self):
        d = dossier_deps([*dossier_matches(), off_table(1, OTHER_ONLY, "2026-10-30", hs=5, as_=0, mid=620)])
        r = dossier(1, deps=d)
        assert 620 not in [w.match_id for w in r.key_wins]
        assert all(call[0] != SHOWCASE for call in d.matches.standings_calls)

    def test_forfeits_are_never_key_wins_but_count_in_form(self):
        extra = [
            off_table(HG_ONLY, PRO_B, "2026-10-28", hs=3, as_=0, mid=630, match_status="forfeit"),
            played(HG_ONLY, 6, "2026-10-29", NORTHEAST, 3, 0, status="forfeit", mid=631),
        ]
        r = dossier(HG_ONLY, deps=dossier_deps([*dossier_matches(), *extra]))
        assert [w.match_id for w in r.key_wins] == [610]
        newest = r.form[0]
        assert (newest.match_id, newest.result, newest.forfeit) == (631, "W", True)
        assert not r.form[1].forfeit
        assert "(forfeit)" in next(f.text for f in r.facts if ":form:last" in f.id)

    def test_top_third_needs_three_teams(self):
        assert not is_top_third(dossier_module.OpponentTable("x", None, 6, None))

    def test_opponent_tables_are_capped(self, monkeypatch):
        monkeypatch.setattr(dossier_module, "MAX_OPPONENT_TABLES", 0)
        r = dossier(HG_ONLY)
        assert r.coverage.opponent_tables_skipped == 1
        # The pro academy needs no table: the win is still reported.
        assert [w.kind for w in r.key_wins] == ["pro_academy_upset"]
        assert r.key_wins[0].opponent_position is None

    def test_skipped_tables_are_counted_once_each(self, monkeypatch):
        monkeypatch.setattr(dossier_module, "MAX_OPPONENT_TABLES", 0)
        rematch = off_table(HG_ONLY, PRO_A, "2026-10-30", hs=1, as_=0, mid=640)
        r = dossier(HG_ONLY, deps=dossier_deps([*dossier_matches(), rematch]))
        assert len(r.key_wins) == 2  # two wins over the same pro academy, one table
        assert r.coverage.opponent_tables_skipped == 1


class TestForm:
    def test_last_five_league_flex_newest_first(self):
        r = dossier(1)
        assert len(r.form) == 5
        dates = [f.date.isoformat() for f in r.form]
        assert dates == sorted(dates, reverse=True)
        assert {f.competition for f in r.form} <= {"League", "Flex"}
        assert "2026-11-01" not in dates  # the friendly
        assert "2026-09-05" not in dates  # the sixth, oldest result
        assert (r.form[0].result, r.form[0].score) == ("W", "4-0")

    def test_other_age_groups_stay_out(self):
        """Team 1 loses every U16 game; its U15 form never sees them."""
        assert all(f.result != "L" for f in dossier(1).form)
        assert all(f.result == "L" for f in dossier(1, U16).form)

    def test_streak(self):
        r = dossier(1)
        streak = next(f for f in r.facts if f.id == r.streak_fact_id)
        assert r.streak_fact_id == f"t1:a{U15}:form:streak"
        assert streak.text == "Team 1 are unbeaten in 6 League/Flex matches."

    def test_no_streak_is_no_fact(self):
        assert dossier(HG_ONLY).streak_fact_id is None


class TestPlayingUp:
    def test_explicit_side_age(self):
        r = dossier(5, None, for_match_id=601)
        assert r.error is None
        assert r.age_group.id == U15
        assert r.context.bracket_age_group.id == U16
        assert r.context.playing_up and not r.context.playing_up_inferred
        assert "playing_up" in r.flags and "playing_up_inferred" not in r.flags
        assert line(r, NORTHEAST).position is not None  # described at its own age

    def test_inferred_from_registrations(self):
        r = dossier(3, None, for_match_id=602)
        assert r.age_group.id == U15
        assert r.context.playing_up and r.context.playing_up_inferred
        assert {"playing_up", "playing_up_inferred"} <= set(r.flags)
        assert "inferred" in next(f.text for f in r.facts if "playing_up" in f.id)

    def test_an_older_side_is_playing_down_not_up(self):
        down = {**match(1, 3, "2026-11-14", NORTHEAST, age=U15, mid=650), "home_age_group_id": U16}
        r = dossier(1, None, deps=dossier_deps([*dossier_matches(), down]), for_match_id=650)
        assert r.error is None
        assert r.age_group.id == U16
        assert not r.context.playing_up and r.context.playing_down
        assert "playing_down" in r.flags and "playing_up" not in r.flags
        assert not any("playing_up" in f.id for f in r.facts)

    def test_a_given_age_that_contradicts_the_recorded_side_is_invalid(self):
        assert dossier(5, U16, for_match_id=601).error.kind == "invalid_args"

    def test_a_given_age_that_agrees_with_the_recorded_side(self):
        r = dossier(5, U15, for_match_id=601)
        assert r.context.playing_up and not r.context.playing_up_inferred

    def test_a_given_age_with_nothing_recorded_is_inferred(self):
        r = dossier(3, U15, for_match_id=602)
        assert r.context.playing_up and r.context.playing_up_inferred
        text = next(f.text for f in r.facts if "playing_up" in f.id)
        assert "inferred" in text and "registration" not in text

    def test_a_match_from_another_season_is_invalid(self):
        old = {**match(1, 2, "2025-11-14", NORTHEAST, mid=660), "season_id": 6}
        r = dossier(1, None, deps=dossier_deps([*dossier_matches(), old]), for_match_id=660)
        assert r.error.kind == "invalid_args"
        assert "current season" in r.error.message

    def test_a_team_registered_at_the_bracket_is_not_playing_up(self):
        r = dossier(8, None, for_match_id=602)
        assert r.age_group.id == U16
        assert not r.context.playing_up
        assert "playing_up" not in r.flags

    def test_detect_playing_up_is_ambiguous_with_two_lower_ages(self):
        mappings = [{"age_groups": {"id": 13, "name": "U13"}}, {"age_groups": {"id": 14, "name": "U14"}}]
        m = {"age_group_id": 15, "age_group_name": "U15", "home_team_id": 1, "away_team_id": 2}
        assert detect_playing_up(m, 1, mappings) == (15, 15, False)
        assert detect_playing_up(m, 1, mappings[:1]) == (13, 15, False)


class TestFacts:
    def test_fact_ids_do_not_depend_on_the_match(self):
        d = dossier_deps()
        plain = dossier(1, deps=d)
        for_match = dossier(1, None, deps=d, for_match_id=501)
        assert [f.id for f in plain.facts] == [f.id for f in for_match.facts]
        assert all(f.id.startswith(f"t1:a{U15}:") for f in plain.facts)
        assert line(plain, NORTHEAST).fact_ids == [
            f"t1:a{U15}:league:{NORTHEAST}:{slug}" for slug in ("pos", "rate", "strength", "clean_sheets")
        ]
        assert plain.key_wins[0].fact_id == f"t1:a{U15}:win:{plain.key_wins[0].match_id}"

    @pytest.mark.parametrize("team_id", [1, 3, 4, 5, HG_ONLY, PRO_B, UNPLAYED])
    def test_no_fact_names_two_conferences(self, team_id):
        for fact in dossier(team_id).facts:
            named = [label for label in CONFERENCE_LABELS if label in fact.text]
            assert len(named) <= 1, fact.text
            assert "better than" not in fact.text

    def test_every_fact_is_about_the_team(self):
        assert {f.team_id for f in dossier(1).facts} == {1}

    def test_coverage(self):
        r = dossier(1)
        assert r.coverage.results_counted == 6
        assert r.coverage.tables_loaded == 2
        assert r.coverage.source == "scraper"
        assert "never compared" in r.coverage.note

    def test_team_carries_club_and_logo(self):
        t = dossier(HG_ONLY).team
        assert (t.club_id, t.club_name, t.logo_url) == (
            HG_ONLY,
            f"Club {HG_ONLY}",
            f"https://cdn.example/{HG_ONLY}.png",
        )


class TestErrors:
    def test_no_age_and_no_match(self):
        assert dossier(1, None).error.kind == "invalid_args"

    def test_unknown_age_group(self):
        assert dossier(1, 99).error.kind == "invalid_args"

    def test_unknown_team(self):
        assert dossier(9999).error.kind == "invalid_args"

    def test_unknown_match(self):
        r = dossier(1, None, for_match_id=9999)
        assert r.error.kind == "invalid_args"

    def test_a_match_the_team_is_not_in(self):
        assert dossier(1, None, for_match_id=503).error.kind == "invalid_args"

    def test_standings_read_failure_is_unavailable(self):
        r = dossier(1, deps=dossier_deps(standings_fail=True))
        assert r.error.kind == "unavailable"
        assert "PostgREST" not in r.error.message
        assert r.conferences is None

    def test_match_read_failure_is_unavailable_not_unknown(self):
        r = dossier(1, None, deps=dossier_deps(match_fail=True), for_match_id=501)
        assert r.error.kind == "unavailable"

    def test_matches_read_failure_is_unavailable(self):
        assert dossier(1, deps=dossier_deps(fail=True)).error.kind == "unavailable"

    def test_test_team_is_hidden_from_a_real_viewer(self):
        assert dossier(TEST_TEAM).error.kind == "invalid_args"
        assert dossier(TEST_TEAM, viewer=TESTER).error is None


def test_empire_is_a_flex_line_for_a_pro_academy():
    assert line(dossier(PRO_A), EMPIRE).kind == "flex"
