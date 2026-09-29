"""get_upcoming_matches (SB-1142): the club's "next game", never a failure dressed as "none"."""

from datetime import UTC, date, datetime

import pytest
from mt_ai_fakes import U15, FakeLeagues, FakeMatches, match_row

from mt_ai.tools import get_upcoming_matches

pytestmark = [pytest.mark.unit, pytest.mark.backend]

IFA, BOSTON, LA_SURF, TSC_TEAM, NOWHERE = 102, 100, 103, 104, 110
# Saturday 3 Oct 2026, 16:00 in Boston.
SAT_AFTERNOON = datetime(2026, 10, 3, 20, 0, tzinfo=UTC)


def season() -> FakeMatches:
    """IFA's autumn, as the scraper left it — no manager, no roster, no events."""
    return FakeMatches(
        [
            match_row(1, "2026-09-26", match_status="completed", home_score=2, away_score=1),
            match_row(2, "2026-10-03", match_status="completed", home_score=0, away_score=0),
            match_row(3, "2026-10-10", scheduled_kickoff="2026-10-10T14:00:00+00:00"),
            match_row(4, "2026-10-04", match_status="cancelled"),
            match_row(5, "2026-10-17", match_status="postponed"),
            match_row(6, "2026-10-24", match_status="tbd", updated_at="2026-09-27T08:00:00+00:00"),
            match_row(7, "2026-10-31", match_status="forfeit"),
            match_row(
                8,
                "2026-10-12",
                home_team_id=BOSTON,
                away_team_id=IFA,
                home_team_name="Boston United",
                away_team_name="IFA",
            ),
        ]
    )


class TestTheDefaultTeam:
    """The common case: a team the scraper knows and nobody manages."""

    def test_returns_what_is_next_in_order(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.error is None
        assert [m.match_id for m in result.matches] == [3, 8, 5, 6]
        assert result.today == date(2026, 10, 3)
        assert result.timezone == "America/New_York"

    def test_finished_and_cancelled_matches_are_not_upcoming(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert {m.status for m in result.matches} == {"scheduled", "postponed", "tbd"}

    def test_a_postponed_fixture_is_kept_and_labelled(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert next(m for m in result.matches if m.match_id == 5).status == "postponed"

    def test_home_and_away_are_from_this_teams_side(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)
        by_id = {m.match_id: m for m in result.matches}

        assert by_id[3].is_home is True
        assert by_id[8].is_home is False

    def test_kickoff_is_given_in_the_clubs_timezone(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)
        kickoff = result.matches[0].kickoff

        assert (kickoff.hour, kickoff.utcoffset().total_seconds()) == (10, -4 * 3600)
        assert result.matches[1].kickoff is None  # unscheduled time stays unknown, not midnight

    def test_provenance_and_freshness_are_reported(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.meta.source == "scraper"
        assert result.meta.as_of == datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
        assert result.meta.coverage is None  # schedules are scraped for every team


class TestNothingVersusUnknown:
    """[] means checked, none scheduled. None means we could not check."""

    def test_an_empty_schedule_is_an_empty_list(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(FakeMatches([])), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.matches == []
        assert result.error is None

    def test_a_failed_read_is_not_an_empty_schedule(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(FakeMatches(fail=True)), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.matches is None
        assert result.error.kind == "unavailable"

    def test_the_dao_is_asked_to_raise_not_to_swallow(self, make_deps, real_viewer):
        """Without raise_on_error the DAO returns [] on failure — exactly the pun to avoid."""
        failing = FakeMatches(fail=True)
        get_upcoming_matches(make_deps(failing), IFA, real_viewer, now=SAT_AFTERNOON)

        assert failing.calls[0]["raise_on_error"] is True

    def test_unreadable_leagues_fail_closed(self, make_deps, real_viewer):
        deps = make_deps(season(), leagues=FakeLeagues([], fail=True))
        result = get_upcoming_matches(deps, IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.matches is None
        assert result.error.kind == "unavailable"


class TestTodayIsTheClubsToday:
    def test_late_evening_is_still_today_for_the_club(self, make_deps, real_viewer):
        # 02:30 UTC Sunday is 22:30 Saturday in Boston: Saturday's game still counts.
        matches = FakeMatches([match_row(1, "2026-10-03")])
        result = get_upcoming_matches(
            make_deps(matches), IFA, real_viewer, now=datetime(2026, 10, 4, 2, 30, tzinfo=UTC)
        )

        assert result.today == date(2026, 10, 3)
        assert [m.match_id for m in result.matches] == [1]
        assert matches.calls[0]["start_date"] == "2026-10-03"

    def test_after_midnight_yesterday_is_gone(self, make_deps, real_viewer):
        matches = FakeMatches([match_row(1, "2026-10-03")])
        result = get_upcoming_matches(
            make_deps(matches), IFA, real_viewer, now=datetime(2026, 10, 4, 4, 30, tzinfo=UTC)
        )

        assert result.today == date(2026, 10, 4)
        assert result.matches == []

    def test_a_west_coast_club_uses_its_own_day(self, make_deps, real_viewer):
        # 05:00 UTC Sunday is 22:00 Saturday in Los Angeles.
        matches = FakeMatches([match_row(1, "2026-10-03", home_team_id=LA_SURF)])
        result = get_upcoming_matches(
            make_deps(matches), LA_SURF, real_viewer, now=datetime(2026, 10, 4, 5, 0, tzinfo=UTC)
        )

        assert result.timezone == "America/Los_Angeles"
        assert [m.match_id for m in result.matches] == [1]

    def test_an_unknown_timezone_falls_back_to_eastern(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(), NOWHERE, real_viewer, now=SAT_AFTERNOON)

        assert result.timezone == "America/New_York"

    def test_a_naive_now_is_read_as_utc(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(), IFA, real_viewer, now=datetime(2026, 10, 4, 2, 30))

        assert result.today == date(2026, 10, 3)


class TestTestPartition:
    def test_test_matches_are_hidden_from_real_viewers(self, make_deps, real_viewer, test_viewer):
        matches = FakeMatches([match_row(1, "2026-10-10"), match_row(2, "2026-10-11", is_test=True)])

        real = get_upcoming_matches(make_deps(matches), IFA, real_viewer, now=SAT_AFTERNOON)
        test = get_upcoming_matches(make_deps(matches), IFA, test_viewer, now=SAT_AFTERNOON)

        assert [m.match_id for m in real.matches] == [1]
        assert [m.match_id for m in test.matches] == [1, 2]

    def test_a_test_team_does_not_exist_for_a_real_viewer(self, make_deps, real_viewer, test_viewer):
        assert get_upcoming_matches(make_deps(), TSC_TEAM, real_viewer).error.kind == "not_found"
        assert get_upcoming_matches(make_deps(), TSC_TEAM, test_viewer, now=SAT_AFTERNOON).error is None


class TestArgumentsAndShape:
    def test_unknown_team_is_not_found(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(), 99999, real_viewer)

        assert result.error.kind == "not_found"
        assert result.matches is None

    @pytest.mark.parametrize("limit", [0, 21])
    def test_limit_is_bounded(self, make_deps, real_viewer, limit):
        assert get_upcoming_matches(make_deps(), IFA, real_viewer, limit=limit).error.kind == "invalid_args"

    def test_results_are_capped_and_say_so(self, make_deps, real_viewer):
        result = get_upcoming_matches(make_deps(season()), IFA, real_viewer, limit=2, now=SAT_AFTERNOON)

        assert [m.match_id for m in result.matches] == [3, 8]
        assert result.meta.truncated is True

    def test_age_group_is_passed_through(self, make_deps, real_viewer):
        matches = FakeMatches([])
        get_upcoming_matches(make_deps(matches), IFA, real_viewer, age_group_id=U15, now=SAT_AFTERNOON)

        assert matches.calls[0]["age_group_id"] == U15

    def test_a_malformed_row_is_skipped_not_fatal(self, make_deps, real_viewer):
        rows = [match_row(1, "2026-10-10"), match_row(2, "not-a-date"), {"id": 3, "match_date": "2026-10-11"}]
        # Row 3 lacks team ids; FakeMatches' team filter would drop it, so bypass it.
        matches = FakeMatches(rows)
        matches.get_all_matches = lambda **_: rows  # type: ignore[method-assign]

        result = get_upcoming_matches(make_deps(matches), IFA, real_viewer, now=SAT_AFTERNOON)

        assert [m.match_id for m in result.matches] == [1]
        assert result.error is None

    def test_a_manager_entered_friendly_makes_provenance_mixed(self, make_deps, real_viewer):
        matches = FakeMatches([match_row(1, "2026-10-10"), match_row(2, "2026-10-11", source="manual")])
        result = get_upcoming_matches(make_deps(matches), IFA, real_viewer, now=SAT_AFTERNOON)

        assert result.meta.source == "mixed"
