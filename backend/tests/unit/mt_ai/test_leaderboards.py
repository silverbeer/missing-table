"""Cross-conference leaderboards (SB-1781): counting, ranking and gathering.

The default fixture is MT's normal team: scraped results and nothing else.
"""

from datetime import date
from fractions import Fraction

import pytest
from leaderboards_fakes import (
    CURRENT,
    FLEX,
    FLEX_TYPE,
    FUTURE,
    HG,
    LEAGUE_TYPE,
    LEAGUES,
    NORTHEAST,
    PAST,
    SOUTHEAST,
    TURNPIKE,
    U13,
    U15,
    U16,
    FakeSeasons,
    default_results,
    deps,
    full_season,
    result,
)

from mt_tools.leaderboards import (
    MIN_GP,
    NOT_A_RANKING,
    TeamTally,
    build_boards,
    conference_of,
    get_leaderboards,
    rank_rows,
    split_min_gp,
    tally,
    unranked_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.backend]


def tt(team_id: int, *, w=0, d=0, l=0, gf=0, ga=0, conf: str | None = "Northeast", **kw) -> TeamTally:
    t = TeamTally(team_id=team_id, name=f"Team {team_id}", gp=w + d + l, w=w, d=d, l=l, gf=gf, ga=ga, **kw)
    if conf:
        t.divisions[conf] = t.gp or 1
    return t


def board(boards, key):
    return next(b for b in boards if b.key == key)


def ranks(b) -> list[tuple[int | None, int]]:
    return [(r.rank, r.team.id) for r in b.rows]


# --- ranking ---------------------------------------------------------------------


class TestRankRows:
    def test_ties_share_a_rank_and_the_next_skips(self):
        assert [r for r, _ in rank_rows([9, 7, 9, 3], lambda v: v)] == [1, 1, 3, 4]

    def test_lower_is_better(self):
        assert rank_rows([3, 1, 2], lambda v: v, higher=False) == [(1, 1), (2, 2), (3, 3)]

    def test_per_game_values_tie_exactly(self):
        """2/3 and 4/6 are the same rate; a float would make them a coin flip."""
        got = rank_rows([Fraction(2, 3), Fraction(4, 6), Fraction(7, 10)], lambda v: v)
        assert [r for r, _ in got] == [1, 2, 2]

    def test_empty(self):
        assert rank_rows([], lambda v: v) == []


class TestSplitMinGp:
    def test_cut(self):
        ranked, too_few = split_min_gp([tt(1, w=MIN_GP), tt(2, w=MIN_GP - 1)])
        assert [t.team_id for t in ranked] == [1]
        assert [t.team_id for t in too_few] == [2]


# --- boards ----------------------------------------------------------------------


class TestBuildBoards:
    def test_every_board_is_there(self):
        keys = [b.key for b in build_boards([tt(1, w=6)])]
        assert keys == ["pts", "ppg", "gf", "gf_pg", "ga", "ga_pg", "gd", "gd_pg", "unbeaten", "pro_wins"]

    def test_points_tie_share_rank_one(self):
        boards = build_boards([tt(1, w=4, l=2), tt(2, w=4, l=2), tt(3, w=3, d=2, l=1)])
        assert ranks(board(boards, "pts")) == [(1, 1), (1, 2), (3, 3)]
        assert board(boards, "pts").rows[0].value == 12

    @pytest.mark.parametrize("key", ["pts", "ppg", "gf", "gf_pg", "ga", "ga_pg", "gd", "gd_pg", "unbeaten"])
    def test_every_board_needs_min_gp(self, key):
        few = tt(1, w=MIN_GP - 1, gf=20)  # perfect, but too few games to rank anywhere
        enough = tt(2, w=3, d=3, gf=6, ga=6)
        b = board(build_boards([few, enough]), key)
        assert ranks(b) == [(1, 2)]
        assert b.unranked_count == 1

    def test_one_game_and_nothing_conceded_never_tops_fewest_against(self):
        """The case the cut exists for: one clean sheet is not the best defence."""
        one_game = tt(1, w=1, ga=0)
        season = tt(2, w=4, l=2, ga=9)
        ga = board(build_boards([one_game, season]), "ga")
        assert ranks(ga) == [(1, 2)]
        assert ga.unranked_count == 1
        listed, count = unranked_rows([one_game, season])
        assert [(r.rank, r.team.id, r.value) for r in listed] == [(None, 1, None)]
        assert count == 1

    def test_per_game_value_is_rounded_for_show_ranked_exactly(self):
        boards = build_boards([tt(1, w=4, d=2, l=1), tt(2, w=6, d=1)])  # 14/7 = 2.0, 19/7
        ppg = board(boards, "ppg")
        assert [(r.team.id, r.value) for r in ppg.rows] == [(2, 2.71), (1, 2.0)]

    def test_goals_against_fewest_first(self):
        boards = build_boards([tt(1, w=6, ga=5), tt(2, w=6, ga=0), tt(3, w=6, ga=2)])
        assert ranks(board(boards, "ga")) == [(1, 2), (2, 3), (3, 1)]
        assert board(boards, "ga").better == "lower"

    def test_goal_difference(self):
        boards = build_boards([tt(1, w=6, gf=1, ga=4), tt(2, w=6, gf=3, ga=0)])
        assert [(r.team.id, r.value) for r in board(boards, "gd").rows] == [(2, 3), (1, -3)]

    def test_unbeaten_needs_no_losses(self):
        long_run = tt(1, w=4, d=MIN_GP - 4)
        short_run = tt(2, w=2)
        lost_once = tt(3, w=9, l=1)
        b = board(build_boards([long_run, short_run, lost_once]), "unbeaten")
        assert ranks(b) == [(1, 1)]
        assert b.rows[0].value == MIN_GP
        assert b.unranked_count == 1  # team 2: unbeaten, too few games; team 3 lost

    def test_no_conference_is_flagged_not_dropped(self):
        flex_only = tt(7, w=6, conf=None)
        boards = build_boards([flex_only, tt(1, w=1, l=5)])
        row = board(boards, "pts").rows[0]
        assert row.team.id == 7
        assert row.conference is None
        assert row.no_conference is True
        assert board(boards, "pts").rows[1].conference == "Northeast"

    def test_no_conference_is_flagged_when_unranked_too(self):
        row = unranked_rows([tt(7, w=1, conf=None)])[0][0]
        assert row.no_conference is True

    def test_a_team_that_never_met_a_pro_academy_is_off_the_pro_board(self):
        teams = [
            tt(1, w=6, pro_gp=2, pro_w=1),
            tt(2, w=6, pro_gp=1, pro_w=0),
            tt(3, w=6),
            tt(4, w=1, pro_gp=1, pro_w=1),
        ]
        pro = board(build_boards(teams), "pro_wins")
        assert [(r.team.id, r.value, r.pro_games) for r in pro.rows] == [(1, 1, 2), (2, 0, 1)]
        # Team 4 played a pro academy but has too few games; team 3 never did.
        assert pro.unranked_count == 1

    def test_limit_keeps_a_tie_at_the_cut(self):
        boards = build_boards([tt(1, w=6), tt(2, w=5, l=1), tt(3, w=5, l=1), tt(4, w=4, l=2)], limit=2)
        assert ranks(board(boards, "pts")) == [(1, 1), (2, 2), (2, 3)]

    def test_tiny_pool(self):
        boards = build_boards([tt(1, w=1)])
        assert all(b.rows == [] for b in boards)
        assert board(boards, "pts").unranked_count == 1
        assert [r.team.id for r in unranked_rows([tt(1, w=1)])[0]] == [1]

    def test_tiny_pool_with_enough_games(self):
        assert ranks(board(build_boards([tt(1, w=6)]), "pts")) == [(1, 1)]

    def test_empty_age_group(self):
        boards = build_boards([])
        assert all(b.rows == [] and b.unranked_count == 0 for b in boards)
        assert unranked_rows([]) == ([], 0)

    def test_unranked_is_listed_once_most_games_first_and_capped(self):
        teams = [tt(i, w=i % MIN_GP) for i in range(1, 12)] + [tt(99, w=MIN_GP)]
        listed, count = unranked_rows(teams, limit=3)
        assert count == 10  # 1..11 except 6, which has not played; 99 is ranked
        # Most games first, then by name ("Team 11" before "Team 5").
        assert [(r.team.id, r.gp) for r in listed] == [(11, 5), (5, 5), (10, 4)]
        assert all(r.rank is None and r.value is None for r in listed)

    def test_every_row_carries_gp(self):
        row = board(build_boards([tt(1, w=3, d=2, l=1)]), "pts").rows[0]
        assert (row.gp, row.w, row.d, row.l) == (6, 3, 2, 1)


# --- tally -----------------------------------------------------------------------


class TestTally:
    def test_record_and_goals(self):
        t = tally([result(1, 2, 2, 0), result(2, 1, 1, 1)], U15, home_league_id=HG).teams
        assert (t[1].w, t[1].d, t[1].l, t[1].gf, t[1].ga, t[1].points) == (1, 1, 0, 3, 1, 4)
        assert (t[2].w, t[2].d, t[2].l) == (0, 1, 1)

    def test_a_shootout_does_not_turn_a_draw_into_a_win(self):
        m = result(1, 7, 1, 1, TURNPIKE, home_penalty_score=4, away_penalty_score=3)
        t = tally([m], U15).teams
        assert (t[1].w, t[1].d) == (0, 1)
        assert t[1].points == 1

    def test_forfeit_counts(self):
        t = tally([result(1, 2, 3, 0, status="forfeit")], U15).teams
        assert t[1].w == 1

    def test_unplayed_statuses_are_ignored(self):
        got = tally([result(1, 2, 0, 0, status="scheduled"), result(1, 2, 1, 0, status="cancelled")], U15)
        assert got.teams == {}
        assert got.matches == 0

    def test_a_match_without_a_score_is_skipped_and_counted(self):
        got = tally([result(1, 2, None, None), result(1, 2, 1, 0)], U15)
        assert got.matches == 1
        assert got.without_score == 1
        assert got.teams[1].gp == 1

    def test_only_league_and_flex(self):
        got = tally([result(1, 2, 5, 0, mtype="Friendly")], U15)
        assert got.teams == {}

    def test_a_side_counts_at_the_age_it_fielded(self):
        """Team 2 played up at U16 in a U15 match: its line is not a U15 line."""
        got = tally([result(1, 2, 2, 1, away_age_group_id=U16)], U15)
        assert set(got.teams) == {1}
        assert got.sides_other_age_group == 1

    def test_conference_is_the_homegrown_division_played_most(self):
        rows = [
            result(1, 2, 1, 0, NORTHEAST),
            result(1, 3, 1, 0, NORTHEAST),
            result(1, 5, 1, 0, SOUTHEAST),
            result(1, 7, 1, 0, TURNPIKE),  # Flex: never a conference
        ]
        t = tally(rows, U15, home_league_id=HG).teams
        assert conference_of(t[1]) == "Northeast"
        assert conference_of(t[7]) is None

    def test_pro_academy_games(self):
        t = tally([result(1, 8, 2, 0, TURNPIKE), result(8, 1, 1, 0, TURNPIKE)], U15, pro_team_ids={8}).teams
        assert (t[1].pro_gp, t[1].pro_w) == (2, 1)

    def test_a_hidden_team_has_no_line_but_its_opponent_keeps_the_game(self):
        t = tally([result(1, 9, 2, 0)], U15, visible=lambda team_id: team_id != 9).teams
        assert set(t) == {1}
        assert t[1].w == 1


# --- gathering -------------------------------------------------------------------


class TestGetLeaderboards:
    def test_reads_homegrown_and_its_flex_played_league_and_flex(self):
        d = deps()
        got = get_leaderboards(d, "Homegrown", "U15")
        assert got.error is None
        call = d.matches.calls[0]
        assert call["season_id"] == 7
        assert call["age_group_id"] == U15
        assert sorted(call["league_ids"]) == [HG, FLEX]
        # From leagues.match_type_id, not hardcoded ids.
        assert sorted(call["match_type_ids"]) == [LEAGUE_TYPE, FLEX_TYPE]
        assert set(call["statuses"]) == {"completed", "forfeit"}
        assert call["include_test"] is False

    def test_coverage_states_teams_and_that_it_is_not_a_ranking(self):
        got = get_leaderboards(deps(), "Homegrown", "U15")
        cov = got.coverage
        assert cov.teams == 8
        assert cov.matches == 8
        assert cov.conferences == 2
        assert cov.min_gp == MIN_GP
        assert cov.competitions_present == ["League", "Flex"]
        assert cov.competitions_absent == []
        assert cov.teams_without_conference == 2  # 7 (Flex only) and 8 (pro academy, Flex only)
        assert NOT_A_RANKING in cov.note
        assert "8 teams" in cov.note
        assert "shootout points are not counted" in cov.note

    def test_the_points_board_says_shootouts_are_draws(self):
        assert "shootouts count as draws" in board(get_leaderboards(deps(), "Homegrown", "U15").boards, "pts").title

    def test_every_row_has_gp_and_conference(self):
        got = get_leaderboards(deps(full_season()), "Homegrown", "U15")
        pts = board(got.boards, "pts")
        assert pts.rows[0].team.id == 1
        assert pts.rows[0].team.club_name == "Club 1"
        assert pts.rows[0].conference == "Northeast"
        flex_only = next(r for r in pts.rows if r.team.id == 7)
        assert flex_only.no_conference and flex_only.gp == 12

    def test_rows_carry_the_club_id_and_logo_null_when_absent(self):
        got = get_leaderboards(deps(full_season()), "Homegrown", "U15")
        rows = {r.team.id: r for r in board(got.boards, "pts").rows}
        assert (rows[1].club_id, rows[1].club_logo_url) == (1, "https://logos/club1.png")
        assert (rows[2].club_id, rows[2].club_logo_url) == (2, None)
        early = get_leaderboards(deps(), "Homegrown", "U15")
        first = next(r for r in early.unranked if r.team.id == 1)
        assert first.club_logo_url == "https://logos/club1.png"

    def test_pure_rows_without_club_lookups_are_null(self):
        rows = build_boards([tt(1, w=6)])[0].rows
        assert (rows[0].club_id, rows[0].club_logo_url) == (None, None)

    def test_early_season_everyone_is_listed_unranked_once(self):
        got = get_leaderboards(deps(), "Homegrown", "U15", limit=3)
        assert all(b.rows == [] for b in got.boards)
        assert board(got.boards, "pts").unranked_count == 8
        assert got.unranked_count == 8
        assert len(got.unranked) == 3  # capped at limit
        assert all(r.rank is None for r in got.unranked)
        assert got.unranked[0].team.id == 1  # most games first

    def test_a_side_playing_up_into_another_age_groups_match_counts_at_its_own_age(self):
        """Team 2 fielded its U15 side in a U16 match: a U15 game for team 2, nothing for team 1."""
        rows = [*full_season(), result(1, 2, 3, 0, age=U16, away_age_group_id=U15)]
        got = get_leaderboards(deps(rows), "Homegrown", "U15")
        base = get_leaderboards(deps(full_season()), "Homegrown", "U15")
        gp = {r.team.id: r.gp for r in board(got.boards, "pts").rows}
        before = {r.team.id: r.gp for r in board(base.boards, "pts").rows}
        assert gp[2] == before[2] + 1
        assert gp[1] == before[1]
        assert got.coverage.sides_other_age_group == base.coverage.sides_other_age_group + 1

    def test_pro_board_from_clubs_pro_academy(self):
        pro = board(get_leaderboards(deps(full_season()), "Homegrown", "U15").boards, "pro_wins")
        assert {(r.team.id, r.value, r.pro_games) for r in pro.rows} == {(2, 6, 6), (7, 6, 6)}

    def test_a_competition_with_no_results_is_named(self):
        rows = [result(10, 11, 1, 0, age=U13)]
        got = get_leaderboards(deps(rows), "Homegrown", "U13")
        assert got.coverage.competitions_absent == ["Flex"]
        assert "No Flex results at U13" in got.coverage.note

    def test_empty_age_group_is_an_answer_not_an_error(self):
        got = get_leaderboards(deps([]), "Homegrown", "U15")
        assert got.error is None
        assert got.reason
        assert got.coverage.teams == 0
        assert board(got.boards, "pts").rows == []
        assert got.unranked == []
        assert got.unranked_count == 0

    def test_a_test_team_is_never_on_a_board(self):
        rows = [*default_results(), result(9, 1, 0, 4)]
        got = get_leaderboards(deps(rows), "Homegrown", "U15")
        assert all(r.team.id != 9 for r in [*got.unranked, *(r for b in got.boards for r in b.rows)])

    def test_past_season_by_name(self):
        d = deps()
        got = get_leaderboards(d, "Homegrown", "U15", season="2025-2026")
        assert got.season.id == PAST["id"]
        assert d.matches.calls[0]["season_id"] == PAST["id"]

    def test_without_a_current_season_the_one_spanning_today_stands_in(self):
        """get_current_season swallows errors: None is not 'pick the newest row'."""
        seasons = FakeSeasons(current=None, seasons=[FUTURE, CURRENT, PAST])
        got = get_leaderboards(deps(seasons=seasons), "Homegrown", "U15", today=date(2026, 11, 26))
        assert got.season.id == CURRENT["id"]

    def test_without_a_current_season_or_one_spanning_today_it_is_unavailable(self):
        seasons = FakeSeasons(current=None, seasons=[FUTURE, CURRENT, PAST])
        got = get_leaderboards(deps(seasons=seasons), "Homegrown", "U15", today=date(2027, 7, 15))
        assert got.error.kind == "unavailable"
        assert got.boards is None

    def test_a_child_league_is_refused_with_the_top_level_ones(self):
        got = get_leaderboards(deps(), "Flex", "U15")
        assert got.error.kind == "invalid_args"
        assert got.error.message == "league must be one of Academy, Homegrown."

    def test_a_league_with_no_match_type_is_unavailable(self):
        leagues = [{**lg, "match_type_id": None} for lg in LEAGUES]
        got = get_leaderboards(deps(leagues=leagues), "Homegrown", "U15")
        assert got.error.kind == "unavailable"

    def test_names_are_case_insensitive(self):
        assert get_leaderboards(deps(), "homegrown", "u15").error is None

    @pytest.mark.parametrize(
        ("kwargs", "needle"),
        [
            ({"league": "Nowhere"}, "league must be one of"),
            ({"age_group": "U99"}, "age_group must be one of"),
            ({"season": "1999-2000"}, "No season named"),
            ({"limit": 0}, "limit"),
            ({"limit": 51}, "limit"),
            ({"league": "TSC League"}, "league must be one of"),
        ],
    )
    def test_invalid_args(self, kwargs, needle):
        got = get_leaderboards(deps(), **{"league": "Homegrown", "age_group": "U15", **kwargs})
        assert got.error.kind == "invalid_args"
        assert needle in got.error.message
        assert got.boards is None

    def test_failed_read_is_unavailable_without_details(self):
        got = get_leaderboards(deps(fail=True), "Homegrown", "U15")
        assert got.error.kind == "unavailable"
        assert "PostgREST" not in got.error.message
        assert got.boards is None

    def test_failed_league_read_is_unavailable(self):
        got = get_leaderboards(deps(leagues_fail=True), "Homegrown", "U15")
        assert got.error.kind == "unavailable"
