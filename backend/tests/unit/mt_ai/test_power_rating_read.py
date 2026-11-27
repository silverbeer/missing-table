"""The MT Power Rating as served (SB-1808): views, movement, coverage, the team panel.

The default store has no run: before launch that is every age group, and it is
an answer (200, `teams` []), not an error.
"""

import json
from datetime import date

import pytest
from leaderboards_fakes import PRO_CLUB, SOUTHEAST
from power_rating_fakes import (
    FakePowerRating,
    conference_world,
    delta,
    deps,
    national_world,
    rating,
    run,
    score,
)

from mt_tools.power_rating_read import (
    coverage_note,
    get_power_rating,
    get_power_rating_team,
    weekly_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.backend]

TODAY = date(2026, 11, 27)


def ranking(store=None, **kwargs):
    return get_power_rating(deps(store), "U15", today=TODAY, **kwargs)


def by_team(result) -> dict:
    return {t.team_id: t for t in result.teams}


class TestNationalView:
    def test_ranked_by_national_rank_with_tiers(self):
        got = ranking(national_world())
        assert got.error is None
        assert got.view == "national"
        assert got.publication.national is True
        assert got.publication.reason is None
        assert [t.key for t in got.tiers] == ["elite", "contender", "above_average"]
        assert [t.min for t in got.tiers] == [1700, 1600, 1500]
        assert [t.team_id for t in got.teams] == [1, 2, 8, 5, 6]
        top = got.teams[0]
        assert (top.rank, top.rating, top.tier, top.conference, top.conference_rank) == (
            1,
            1754,
            "elite",
            "Northeast",
            1,
        )
        assert top.comparable_nationally is True

    def test_a_team_outside_the_main_island_has_no_national_rank(self):
        six = by_team(ranking(national_world()))[6]
        assert six.rank is None
        assert six.comparable_nationally is False
        assert six.conference == "Southeast"

    def test_rows_carry_club_and_pro_academy(self):
        teams = by_team(ranking(national_world()))
        assert teams[1].club_id == 1
        assert teams[1].club_logo_url == "https://logos/club1.png"
        assert teams[2].club_logo_url is None
        assert teams[8].club_id == PRO_CLUB
        assert teams[8].pro_academy is True
        assert teams[1].pro_academy is False
        assert teams[2].badges == ["provisional"]

    def test_test_teams_are_never_shown(self):
        got = ranking(national_world())
        assert 9 not in by_team(got)
        assert got.coverage.teams_in_pool == 6

    def test_conference_view_of_a_national_run_has_no_tiers(self):
        got = ranking(national_world(), view="conference")
        assert got.view == "conference"
        assert got.tiers == []
        assert all(t.tier is None and t.rank is None for t in got.teams)
        assert got.publication.national is True


class TestConferenceView:
    def test_national_asked_on_a_conference_run_gets_conference_lists_and_the_reason(self):
        got = ranking(conference_world(), view="national")
        assert got.view == "conference"
        assert got.publication.national is False
        assert "90%" in got.publication.reason
        assert got.tiers == []

    def test_grouped_by_conference_then_conference_rank(self):
        got = ranking(conference_world())
        assert [(t.conference, t.conference_rank, t.team_id) for t in got.teams] == [
            ("Northeast", 1, 1),
            ("Northeast", 2, 3),
            ("Southeast", 1, 5),
        ]
        assert all(t.rank is None and t.tier is None and not t.comparable_nationally for t in got.teams)
        assert got.conferences == ["Northeast", "Southeast"]

    def test_a_conference_filter(self):
        got = ranking(conference_world(), conference="southeast")
        assert got.conference == "Southeast"
        assert [t.team_id for t in got.teams] == [5]
        assert got.unranked == []
        # The denominator is still the whole run's.
        assert got.coverage.teams_in_pool == 4

    def test_an_unknown_conference_is_invalid_args(self):
        got = ranking(conference_world(), conference="Atlantis")
        assert got.error.kind == "invalid_args"
        assert "Northeast, Southeast" in got.error.message


class TestMovement:
    def test_compared_with_the_run_a_week_before_the_latest(self):
        got = ranking(national_world())
        assert got.movement_since.run_id == 10  # Nov 20, not the Nov 25 run
        one, two, eight = (by_team(got)[i] for i in (1, 2, 8))
        assert (one.rank_change_7d, one.rating_change_7d) == (2, 12)
        assert (two.rank_change_7d, two.rating_change_7d) == (-1, -9)  # 1651 - 1660, the shown numbers
        assert (eight.rank_change_7d, eight.rating_change_7d) == (-1, 10)

    def test_a_team_not_in_last_weeks_run_has_null_movement_not_zero(self):
        five = by_team(ranking(national_world()))[5]
        assert five.rank_change_7d is None
        assert five.rating_change_7d is None

    def test_no_run_a_week_earlier_is_null_movement(self):
        got = ranking(conference_world())
        assert got.movement_since is None
        assert all(t.rank_change_7d is None and t.rating_change_7d is None for t in got.teams)

    def test_a_run_under_a_week_old_is_not_the_comparison(self):
        store = FakePowerRating(
            runs=[run(1, "2026-11-24"), run(2, "2026-11-27")],
            ratings={1: [rating(1, 1500.0, 8, conference_rank=2)], 2: [rating(1, 1600.0, 8, conference_rank=1)]},
        )
        got = ranking(store)
        assert got.movement_since is None
        assert got.teams[0].rank_change_7d is None

    def test_conference_view_moves_in_conference_places(self):
        store = FakePowerRating(
            runs=[run(1, "2026-11-13"), run(2, "2026-11-27")],
            ratings={
                1: [rating(1, 1500.0, 8, conference_rank=3), rating(5, 1500.0, 8, conference_rank=1)],
                2: [
                    rating(1, 1600.0, 8, conference_rank=1),
                    rating(5, 1510.0, 8, conf=SOUTHEAST, conference_rank=1),
                ],
            },
        )
        teams = by_team(ranking(store))
        assert (teams[1].rank_change_7d, teams[1].rating_change_7d) == (2, 100)
        # Changed conference: its places are not comparable; its points still are.
        assert (teams[5].rank_change_7d, teams[5].rating_change_7d) == (None, 10)


class TestUnrankedAndCoverage:
    def test_unranked_teams_are_listed_with_what_they_need_never_placed(self):
        got = ranking(national_world())
        assert [u.team_id for u in got.unranked] == [7]
        seven = got.unranked[0]
        assert (seven.mp, seven.needed, seven.conference) == (4, 6, None)
        assert 7 not in by_team(got)

    def test_unranked_most_matches_first(self):
        store = FakePowerRating(
            runs=[run(1, "2026-11-27")],
            ratings={1: [rating(1, 1500.0, 2), rating(2, 1510.0, 5), rating(3, 1490.0, 0)]},
        )
        got = ranking(store)
        assert got.teams == []
        assert [(u.team_id, u.mp) for u in got.unranked] == [(2, 5), (1, 2), (3, 0)]
        assert got.coverage.ranked == 0
        assert got.coverage.unranked_count == 3

    def test_coverage_states_its_denominator(self):
        cov = ranking(national_world()).coverage
        assert (cov.teams_in_pool, cov.ranked, cov.unranked_count, cov.matches_counted) == (6, 5, 1, 40)
        assert cov.matches_excluded["out_of_pool_opponent"] == 2
        assert cov.min_matches == 6
        assert cov.note == (
            "MT Power Rating from 6 Homegrown U15 teams in MT, rated on 40 matches; 5 with 6 or more matches "
            "are ranked. Conferences meet only at Flex and national events."
        )

    def test_conference_note_says_not_comparable(self):
        assert ranking(conference_world()).coverage.note.endswith(
            "Shown as conference lists: not yet comparable nationally."
        )

    def test_note_singulars(self):
        note = coverage_note(1, 1, 1, "Homegrown", "U17", national_view=True)
        assert note.startswith("MT Power Rating from 1 Homegrown U17 team in MT, rated on 1 match; 1 with 6")
        assert "1 with 6 or more matches is ranked" in note

    def test_matches_never_games(self):
        for result in (ranking(national_world()), ranking(conference_world()), ranking()):
            assert "game" not in json.dumps(result.model_dump(mode="json")).lower()


class TestNoRun:
    def test_no_run_yet_is_an_answer(self):
        got = ranking()
        assert got.error is None
        assert got.teams == []
        assert got.unranked == []
        assert got.run is None
        assert got.reason == "No Power Rating has been computed for Homegrown U15 in 2026-2027 yet."
        assert got.publication.national is False

    def test_a_run_with_nothing_rated(self):
        got = ranking(FakePowerRating(runs=[run(1, "2026-11-27", matches_counted=0)], ratings={1: []}))
        assert got.teams == []
        assert got.coverage.teams_in_pool == 0
        assert got.reason == "No rated matches at U15 Homegrown in 2026-2027 yet."


class TestArgsAndFailures:
    def test_unknown_age_group_is_invalid_args(self):
        got = get_power_rating(deps(national_world()), "U99", today=TODAY)
        assert got.error.kind == "invalid_args"

    def test_a_child_league_is_invalid_args(self):
        got = get_power_rating(deps(national_world()), "U15", "Flex", today=TODAY)
        assert got.error.kind == "invalid_args"

    def test_an_unknown_view_is_invalid_args(self):
        assert ranking(national_world(), view="global").error.kind == "invalid_args"

    def test_a_failed_read_is_unavailable_without_details(self):
        got = ranking(FakePowerRating(fail=True))
        assert got.error.kind == "unavailable"
        assert got.teams is None
        assert "PostgREST" not in got.error.message

    def test_without_a_store_it_is_unavailable(self):
        from dataclasses import replace

        from leaderboards_fakes import deps as league_deps

        got = get_power_rating(replace(league_deps(), power_rating=None), "U15", today=TODAY)
        assert got.error.kind == "unavailable"

    def test_the_payload_is_read_by_run_id(self):
        store = national_world()
        ranking(store)
        assert store.payload_reads == [12, 10]


# --- the team panel ----------------------------------------------------------------


def team_world() -> FakePowerRating:
    """Team 1 across three runs: two in one week (Nov 23, Nov 27), one the week before."""
    latest = [
        rating(1, 1642.0, 6, rank=2, conference_rank=1, sos=1538.0),
        rating(2, 1700.0, 6, rank=1, conference_rank=2, sos=1490.0),
        rating(5, 1500.0, 6, conf=SOUTHEAST, rank=3, conference_rank=1, sos=1560.0),
        rating(3, 1480.0, 4),
    ]
    return FakePowerRating(
        runs=[
            run(1, "2026-11-16", national=True),
            run(2, "2026-11-23", national=True),
            run(3, "2026-11-27", national=True),
        ],
        ratings={1: [rating(1, 1550.0, 2, rank=4)], 2: [rating(1, 1600.0, 4, rank=3)], 3: latest},
        deltas={
            3: [
                delta(101, 1, 2, 24.0, 1.0, 0.41),
                delta(102, 1, 5, -21.0, 0.0, 0.70),
                delta(103, 1, 3, 3.0, 0.5),
                delta(104, 1, 4, 13.0, 1.0),
                delta(105, 1, 2, -30.4, 0.5),
                delta(106, 1, 6, 1.0, 1.0),
            ]
        },
        matches=[
            score(101, "2026-11-01", 1, 2, 3, 0),
            score(102, "2026-11-08", 5, 1, 1, 0),
            score(103, "2026-11-15", 3, 1, 1, 1),
            score(104, "2026-11-02", 1, 4, 2, 0),
            score(105, "2026-11-22", 2, 1, 2, 2, hp=3, ap=4),
            # 106 is gone: its date and score are absent, not 0-0.
        ],
    )


def team(team_id=1, store=None, age="U15"):
    return get_power_rating_team(deps(store if store is not None else team_world()), team_id, age, today=TODAY)


class TestTeam:
    def test_rating_ranks_and_record(self):
        got = team()
        assert got.error is None
        assert got.in_run is True
        assert (got.rating, got.rank, got.conference, got.conference_rank) == (1642, 2, "Northeast", 1)
        assert got.ranked is True
        assert got.needed is None
        assert got.run.id == 3
        assert got.club_logo_url == "https://logos/club1.png"

    def test_the_three_biggest_movers(self):
        movers = team().biggest_movers
        assert [(m.match_id, m.delta) for m in movers] == [(105, -30.4), (101, 24.0), (102, -21.0)]
        drew, beat, lost = movers
        assert (beat.opponent, beat.result, beat.goals_for, beat.goals_against, beat.expected) == (
            "Team 2",
            "W",
            3,
            0,
            0.41,
        )
        # Away side: the score is from the team's side.
        assert (lost.goals_for, lost.goals_against, lost.result) == (0, 1, "L")
        # A shoot-out is a draw, with the penalties alongside.
        assert (drew.result, drew.goals_for, drew.penalties_for, drew.penalties_against) == ("D", 2, 4, 3)
        assert drew.match_date == date(2026, 11, 22)

    def test_every_delta_oldest_first_and_a_missing_match_is_absent(self):
        deltas = team().deltas
        assert [d.match_id for d in deltas] == [101, 104, 102, 103, 105, 106]
        gone = deltas[-1]
        assert gone.match_date is None
        assert gone.goals_for is None and gone.goals_against is None

    def test_history_is_one_point_per_week(self):
        history = team().history
        assert [(h.run_id, h.rating, h.rank) for h in history] == [(1, 1550, 4), (3, 1642, 2)]

    def test_sos_ranked_toughest_first_nationally(self):
        sos = team().sos
        assert (sos.rating, sos.rank, sos.of, sos.scope) == (1538, 2, 3, "national")

    def test_sos_within_the_conference_without_a_national_list(self):
        store = FakePowerRating(
            runs=[run(1, "2026-11-27")],
            ratings={
                1: [
                    rating(1, 1600.0, 8, conference_rank=1, sos=1480.0),
                    rating(2, 1550.0, 8, conference_rank=2, sos=1520.0),
                    rating(5, 1500.0, 8, conf=SOUTHEAST, conference_rank=1, sos=1700.0),
                ]
            },
        )
        sos = team(store=store).sos
        assert (sos.rank, sos.of, sos.scope) == (2, 2, "conference")

    def test_an_unranked_team_needs_more_matches(self):
        got = team(3)
        assert got.ranked is False
        assert got.needed == 2
        assert got.rank is None
        assert (got.sos.rating, got.sos.rank) == (1500, None)

    def test_a_team_not_in_the_run_is_an_answer(self):
        got = team(6)
        assert got.error is None
        assert got.in_run is False
        assert got.rating is None
        assert got.history is None and got.biggest_movers is None
        assert got.reason == "Team 6 has no rated match at U15 Homegrown in 2026-2027."

    def test_no_run_yet_is_an_answer(self):
        got = team(store=FakePowerRating())
        assert got.in_run is False
        assert got.run is None
        assert "No Power Rating has been computed" in got.reason

    def test_an_unknown_or_test_team_is_invalid_args(self):
        assert team(9999).error.kind == "invalid_args"
        assert team(9).error.kind == "invalid_args"

    def test_a_failed_read_is_unavailable(self):
        got = team(store=FakePowerRating(fail=True))
        assert got.error.kind == "unavailable"
        assert "PostgREST" not in got.error.message

    def test_matches_never_games(self):
        assert "game" not in json.dumps(team().model_dump(mode="json")).lower()


def test_weekly_history_skips_runs_without_the_team():
    runs = [
        {"id": 1, "computed_at": "2026-11-10T10:00:00+00:00"},
        {"id": 2, "computed_at": "2026-11-17T10:00:00+00:00"},
    ]
    points = weekly_history(runs, [{"run_id": 2, "rating": 1510.4, "rank": None, "conference_rank": 3}])
    assert [(p.run_id, p.rating, p.conference_rank) for p in points] == [(2, 1510, 3)]
