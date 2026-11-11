"""Tables ranked by points per match (SB-1623).

MLS NEXT ranks by points per match, not total points: teams play different
numbers of games across League and Flex. The order and tiebreaks below come
from the 2026-27 Allstate Homegrown Division Rules and Regulations, XIII.k-l
(the Academy Division rules say the same):

    https://images.mlssoccer.com/image/upload/v1783990779/assets/MLS_NEXT_HD_Rules_and_Regulations_2026-27_Final_Web_Version_hwmkha.pdf

Tied on points per match: head-to-head (two clubs only), wins per match,
goal difference per match, goals for per match, away GD per match, away GF
per match, home GD per match, home GF per match, then discipline and a coin
toss, which MT does not record.
"""

from itertools import count

from dao.standings import calculate_standings, per_match_stats, rank_table

LEAGUE = {"id": 1, "name": "League", "shootout_points": False}
FLEX = {"id": 5, "name": "Flex", "shootout_points": True}

_ids = count(100)


def team(name: str) -> dict:
    team_id = next(_ids)
    return {"id": team_id, "name": name, "club": {"id": team_id, "name": name}}


def match(home, away, home_score, away_score, match_type=LEAGUE, pens=None) -> dict:
    home_pens, away_pens = pens or (None, None)
    return {
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "match_type": match_type,
        "home_penalty_score": home_pens,
        "away_penalty_score": away_pens,
        "match_date": "2026-10-01",
    }


def vs_filler(side: dict, score: tuple[int, int], *, home: bool = True, **kw) -> dict:
    """A result against a one-off opponent, so it touches no one else's row."""
    other = team(f"filler {next(_ids)}")
    gf, ga = score
    return match(side, other, gf, ga, **kw) if home else match(other, side, ga, gf, **kw)


def order(table: list[dict], *names: str) -> list[str]:
    return [r["team"] for r in table if r["team"] in names]


def row(table: list[dict], name: str) -> dict:
    return next(r for r in table if r["team"] == name)


class TestPointsPerMatch:
    def test_fewer_games_and_a_better_rate_ranks_above_more_points(self) -> None:
        # The U15 New England Flex table that prompted this: IFA 9 from 4
        # (2.25) sits above NEFC 11 from 5 (2.20) on mlssoccer.com.
        ifa, nefc = team("IFA"), team("NEFC")
        matches = [vs_filler(ifa, s) for s in [(2, 0), (2, 0), (2, 0), (0, 1)]]
        matches += [vs_filler(nefc, s) for s in [(1, 0), (1, 0), (1, 0), (1, 1), (1, 1)]]
        table = calculate_standings(matches)
        assert order(table, "IFA", "NEFC") == ["IFA", "NEFC"]
        assert (row(table, "IFA")["points"], row(table, "IFA")["points_per_match"]) == (9, 2.25)
        assert (row(table, "NEFC")["points"], row(table, "NEFC")["points_per_match"]) == (11, 2.2)

    def test_per_match_stats_round_to_two_decimals(self) -> None:
        stats = per_match_stats({"played": 3, "points": 7, "goal_difference": -1, "goals_for": 4, "goals_against": 5})
        assert stats == {
            "points_per_match": 2.33,
            "gd_per_match": -0.33,
            "gf_per_match": 1.33,
            "ga_per_match": 1.67,
        }

    def test_no_games_is_no_rate_not_zero(self) -> None:
        stats = per_match_stats({"played": 0, "points": 0, "goal_difference": 0, "goals_for": 0, "goals_against": 0})
        assert stats == {
            "points_per_match": None,
            "gd_per_match": None,
            "gf_per_match": None,
            "ga_per_match": None,
        }

    def test_a_shootout_win_counts_in_points_per_match(self) -> None:
        a = team("A")
        table = calculate_standings(
            [vs_filler(a, (1, 0), match_type=FLEX), vs_filler(a, (0, 0), match_type=FLEX, pens=(4, 3))]
        )
        assert (row(table, "A")["points"], row(table, "A")["points_per_match"]) == (5, 2.5)

    def test_a_team_with_no_games_sorts_last(self) -> None:
        played = {"team": "B", "played": 1, "points": 0, "wins": 0, "goal_difference": -3, "goals_for": 0}
        unplayed = {"team": "A", "played": 0, "points": 0, "wins": 0, "goal_difference": 0, "goals_for": 0}
        assert [r["team"] for r in rank_table([unplayed, played])] == ["B", "A"]


class TestTiebreaks:
    def test_head_to_head_settles_a_two_club_tie_before_anything_else(self) -> None:
        # Both 2.0 per match. A has the better goal difference, but B beat A.
        a, b = team("A"), team("B")
        matches = [
            match(b, a, 1, 0),
            vs_filler(a, (9, 0)),
            vs_filler(a, (9, 0)),
            vs_filler(b, (1, 0)),
            vs_filler(b, (0, 1)),
        ]
        table = calculate_standings(matches)
        assert row(table, "A")["points_per_match"] == row(table, "B")["points_per_match"] == 2.0
        assert order(table, "A", "B") == ["B", "A"]

    def test_a_level_head_to_head_falls_to_wins_per_match(self) -> None:
        # Drew 1-1 with each other. A: 7 from 4, two wins (0.50 a game).
        # B: 14 from 8, three wins (0.38 a game). Both 1.75 per match.
        a, b = team("A"), team("B")
        matches = [match(a, b, 1, 1)]
        matches += [vs_filler(a, s) for s in [(1, 0), (1, 0), (0, 1)]]
        matches += [vs_filler(b, s) for s in [(1, 0)] * 3 + [(0, 0)] * 4]
        table = calculate_standings(matches)
        assert row(table, "A")["points_per_match"] == row(table, "B")["points_per_match"]
        assert order(table, "A", "B") == ["A", "B"]

    def test_three_way_tie_never_uses_head_to_head(self) -> None:
        # A beat B, B beat C, C beat A, each 1-0; then each won once more.
        # A beat B, but in a three-way tie that counts for nothing: goal
        # difference per match decides, and A's is the worst.
        a, b, c = team("A"), team("B"), team("C")
        matches = [
            match(a, b, 1, 0),
            match(b, c, 1, 0),
            match(c, a, 1, 0),
            vs_filler(a, (1, 0)),
            vs_filler(b, (2, 0)),
            vs_filler(c, (3, 0)),
        ]
        table = calculate_standings(matches)
        assert {row(table, n)["points_per_match"] for n in "ABC"} == {2.0}
        assert order(table, "A", "B", "C") == ["C", "B", "A"]

    def test_wins_per_match_beats_goal_difference(self) -> None:
        # 1.0 per match each: A one win in three, B three draws.
        a, b = team("A"), team("B")
        matches = [vs_filler(a, s) for s in [(1, 0), (0, 3), (0, 3)]]
        matches += [vs_filler(b, s) for s in [(0, 0), (0, 0), (0, 0)]]
        assert order(calculate_standings(matches), "A", "B") == ["A", "B"]

    def test_goal_difference_per_match_not_total(self) -> None:
        # Both 1.67 per match and a third of games won. A: +3 over 3 (1.00 a
        # game). B: +5 over 6 (0.83 a game). Total GD would put B first.
        a, b = team("A"), team("B")
        matches = [vs_filler(a, s) for s in [(3, 0), (0, 0), (0, 0)]]
        matches += [vs_filler(b, s) for s in [(3, 0), (2, 0), (0, 0), (0, 0), (0, 0), (0, 0)]]
        table = calculate_standings(matches)
        assert row(table, "A")["points_per_match"] == row(table, "B")["points_per_match"]
        assert row(table, "B")["goal_difference"] > row(table, "A")["goal_difference"]
        assert order(table, "A", "B") == ["A", "B"]

    def test_goals_for_per_match_after_goal_difference(self) -> None:
        a, b = team("A"), team("B")
        matches = [vs_filler(a, (3, 2)), vs_filler(b, (1, 0))]
        assert order(calculate_standings(matches), "A", "B") == ["A", "B"]

    def test_away_goal_difference_per_match_breaks_what_totals_cannot(self) -> None:
        # Identical overall. A did its scoring away, B at home.
        a, b = team("A"), team("B")
        matches = [
            vs_filler(a, (2, 0), home=False),
            vs_filler(a, (0, 0), home=True),
            vs_filler(b, (2, 0), home=True),
            vs_filler(b, (0, 0), home=False),
        ]
        assert order(calculate_standings(matches), "A", "B") == ["A", "B"]

    def test_a_tie_nothing_recorded_can_break_falls_back_to_name(self) -> None:
        z, a = team("Zeta"), team("Alpha")
        matches = [vs_filler(z, (1, 0)), vs_filler(a, (1, 0))]
        assert order(calculate_standings(matches), "Alpha", "Zeta") == ["Alpha", "Zeta"]

    def test_head_to_head_includes_flex_shootout_points(self) -> None:
        # 0-0 in Flex, B won the shootout: head-to-head B 2, A 1. Both 5 from
        # 3 and a win in three; A has the better goal difference.
        a, b = team("A"), team("B")
        matches = [
            match(a, b, 0, 0, match_type=FLEX, pens=(3, 4)),
            vs_filler(a, (1, 0)),
            vs_filler(a, (0, 0)),
            vs_filler(b, (1, 0)),
            vs_filler(b, (0, 1)),
        ]
        table = calculate_standings(matches)
        assert row(table, "A")["points_per_match"] == row(table, "B")["points_per_match"]
        assert row(table, "A")["goal_difference"] > row(table, "B")["goal_difference"]
        assert order(table, "A", "B") == ["B", "A"]
