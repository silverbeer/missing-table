"""get_recent_results (SB-1526): played matches from the team's side, never "none" for "unknown"."""

from datetime import UTC, date, datetime

import pytest
from mt_ai_fakes import U15, FakeMatches, match_row

from mt_ai.tools import get_recent_results

pytestmark = [pytest.mark.unit, pytest.mark.backend]

IFA, BOSTON, LA_SURF, TSC_TEAM = 102, 100, 103, 104
# Saturday 3 Oct 2026, 16:00 in Boston.
SAT_AFTERNOON = datetime(2026, 10, 3, 20, 0, tzinfo=UTC)


def played(match_id: int, day: str, home: int, away: int, **overrides) -> dict:
    return match_row(match_id, day, match_status="completed", home_score=home, away_score=away, **overrides)


def autumn() -> FakeMatches:
    """IFA's scraped autumn: results, one forfeit, one unscored, one still to come."""
    return FakeMatches(
        [
            played(1, "2026-09-12", 2, 1),  # IFA home win
            played(
                2,
                "2026-09-19",
                3,
                0,
                home_team_id=BOSTON,
                away_team_id=IFA,
                home_team_name="Boston United",
                away_team_name="IFA",
            ),  # IFA away loss
            played(3, "2026-09-26", 1, 1, home_penalty_score=4, away_penalty_score=3),  # draw on pens
            match_row(4, "2026-09-27", match_status="forfeit", home_score=3, away_score=0),
            match_row(5, "2026-10-01", match_status="completed"),  # played, no score recorded
            match_row(6, "2026-10-02", match_status="cancelled", home_score=0, away_score=0),
            match_row(7, "2026-10-10"),  # upcoming
        ]
    )


class TestResultsFromTheTeamsSide:
    def test_newest_first_played_only(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.error is None
        assert [m.match_id for m in result.matches] == [4, 3, 2, 1]
        assert result.today == date(2026, 10, 3)

    def test_win_draw_loss_and_goals_are_this_teams(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, now=SAT_AFTERNOON)
        by_id = {m.match_id: m for m in result.matches}

        assert (by_id[1].result, by_id[1].goals_for, by_id[1].goals_against) == ("W", 2, 1)
        assert (by_id[2].result, by_id[2].goals_for, by_id[2].goals_against, by_id[2].is_home) == (
            "L",
            0,
            3,
            False,
        )
        assert by_id[4].status == "forfeit" and by_id[4].result == "W"

    def test_a_shootout_is_still_a_draw_with_the_shootout_alongside(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, now=SAT_AFTERNOON)
        shootout = next(m for m in result.matches if m.match_id == 3)

        assert shootout.result == "D"
        assert (shootout.home_penalty_score, shootout.away_penalty_score) == (4, 3)

    def test_summary_covers_what_was_returned(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, now=SAT_AFTERNOON)

        s = result.summary
        assert (s.played, s.wins, s.draws, s.losses, s.goals_for, s.goals_against) == (4, 2, 1, 1, 6, 5)


class TestAbsentIsNotZero:
    def test_an_unscored_match_is_left_out_not_counted_as_nil_nil(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert 5 not in [m.match_id for m in result.matches]

    def test_no_played_match_is_an_empty_list(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(FakeMatches([match_row(7, "2026-10-10")])), IFA, real_viewer)

        assert result.matches == []
        assert result.summary.played == 0
        assert result.error is None

    def test_a_failed_read_is_not_an_empty_record(self, make_deps, real_viewer):
        failing = FakeMatches(fail=True)
        result = get_recent_results(make_deps(failing), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.matches is None and result.summary is None
        assert result.error.kind == "unavailable"
        assert failing.calls[0]["raise_on_error"] is True


class TestTodayAndHeadToHead:
    def test_tonights_result_counts_in_the_clubs_day(self, make_deps, real_viewer):
        # 02:30 UTC Sunday is 22:30 Saturday in Boston.
        matches = FakeMatches([played(1, "2026-10-03", 1, 0)])
        result = get_recent_results(make_deps(matches), IFA, real_viewer, now=datetime(2026, 10, 4, 2, 30, tzinfo=UTC))

        assert [m.match_id for m in result.matches] == [1]
        assert matches.calls[0]["end_date"] == "2026-10-03"

    def test_head_to_head_keeps_only_that_opponent(self, make_deps, real_viewer):
        rows = [
            played(1, "2026-09-12", 2, 1),
            played(2, "2026-09-19", 1, 0, away_team_id=LA_SURF, away_team_name="LA Surf"),
        ]
        result = get_recent_results(
            make_deps(FakeMatches(rows)), IFA, real_viewer, opponent_id=BOSTON, now=SAT_AFTERNOON
        )

        assert [m.match_id for m in result.matches] == [1]
        assert result.opponent_id == BOSTON

    def test_unknown_or_self_opponent_is_refused(self, make_deps, real_viewer):
        assert get_recent_results(make_deps(), IFA, real_viewer, opponent_id=99999).error.kind == "not_found"
        assert get_recent_results(make_deps(), IFA, real_viewer, opponent_id=IFA).error.kind == "invalid_args"


class TestArgumentsAndVisibility:
    def test_unknown_team_is_not_found(self, make_deps, real_viewer):
        assert get_recent_results(make_deps(), 99999, real_viewer).error.kind == "not_found"

    @pytest.mark.parametrize("limit", [0, 21])
    def test_limit_is_bounded(self, make_deps, real_viewer, limit):
        assert get_recent_results(make_deps(), IFA, real_viewer, limit=limit).error.kind == "invalid_args"

    def test_results_are_capped_and_say_so(self, make_deps, real_viewer):
        result = get_recent_results(make_deps(autumn()), IFA, real_viewer, limit=2, now=SAT_AFTERNOON)

        assert [m.match_id for m in result.matches] == [4, 3]
        assert result.meta.truncated is True
        assert result.summary.played == 2

    def test_age_group_is_passed_through(self, make_deps, real_viewer):
        matches = FakeMatches([])
        get_recent_results(make_deps(matches), IFA, real_viewer, age_group_id=U15, now=SAT_AFTERNOON)

        assert matches.calls[0]["age_group_id"] == U15

    def test_test_matches_and_teams_are_hidden_from_real_viewers(self, make_deps, real_viewer, test_viewer):
        matches = FakeMatches([played(1, "2026-09-12", 1, 0), played(2, "2026-09-13", 2, 0, is_test=True)])

        real = get_recent_results(make_deps(matches), IFA, real_viewer, now=SAT_AFTERNOON)
        test = get_recent_results(make_deps(matches), IFA, test_viewer, now=SAT_AFTERNOON)

        assert [m.match_id for m in real.matches] == [1]
        assert [m.match_id for m in test.matches] == [2, 1]
        assert get_recent_results(make_deps(), TSC_TEAM, real_viewer).error.kind == "not_found"

    def test_a_malformed_row_is_skipped_not_fatal(self, make_deps, real_viewer):
        rows = [played(1, "2026-09-12", 1, 0), played(2, "not-a-date", 1, 0)]
        matches = FakeMatches(rows)
        matches.get_all_matches = lambda **_: rows  # type: ignore[method-assign]

        result = get_recent_results(make_deps(matches), IFA, real_viewer, now=SAT_AFTERNOON)

        assert [m.match_id for m in result.matches] == [1]
