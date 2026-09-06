"""Shootout points (SB-1027).

MLS NEXT Flex has no draws at U15-U19. A match level after regulation goes to
penalties, and the shootout is worth points: winner 2, loser 1. A regulation
win is still 3. Homegrown League play is the opposite — a draw is 1 point each
(2026-27 Allstate Homegrown Division Rules and Regulations, section k) — and a
Tournament shootout is knockout progression, not points.

So the rule belongs to the competition, not to the match: `match_types.
shootout_points` is the only thing these functions read to decide, never the
competition's name and never the mere presence of a recorded shootout.

The Flex fixtures below are the official 2026 MLS NEXT Flex U17 results as
published on mlssoccer.com (modular11 group tables, read 2026-09-06). The
expected rows are the official table, not a derivation — if the points model
here is wrong, these tests are wrong against the world, not against
themselves.
"""

import pytest

from dao.standings import (
    awards_shootout_points,
    calculate_standings,
    calculate_standings_with_extras,
    get_team_form,
    shootout_competitions,
    shootout_result,
)

LEAGUE = {"id": 1, "name": "League", "shootout_points": False}
FLEX = {"id": 5, "name": "Flex", "shootout_points": True}
TOURNAMENT = {"id": 2, "name": "Tournament", "shootout_points": False}


def team(team_id: int, name: str) -> dict:
    return {"id": team_id, "name": name, "club": {"id": team_id, "name": name}}


def match(home, away, home_score, away_score, match_type=FLEX, pens=None, date="2026-04-25", match_id=0):
    m = {
        "id": match_id,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "match_type": match_type,
        "division_id": 309,
        "match_status": "completed",
        "match_date": date,
        "home_penalty_score": None,
        "away_penalty_score": None,
    }
    if pens is not None:
        m["home_penalty_score"], m["away_penalty_score"] = pens
    return m


def row(table: list[dict], name: str) -> dict:
    return next(r for r in table if r["team"] == name)


# ── 2026 MLS NEXT Flex U17, Group C ─────────────────────────────────────
# Official table: Orlando City SC 8 (2W 0L 1T), NEFC 7 (2W 0L 1T),
# Triangle United 3 (1W 2L), Michigan Futbol Academy 0.
ORLANDO = team(1, "Orlando City SC")
NEFC = team(2, "NEFC")
TRIANGLE = team(3, "Triangle United Soccer Association")
MFA = team(4, "Michigan Futbol Academy")

GROUP_C = [
    match(NEFC, TRIANGLE, 3, 0, date="2026-04-25", match_id=22965),
    match(ORLANDO, MFA, 5, 1, date="2026-04-25", match_id=22543),
    match(TRIANGLE, ORLANDO, 0, 1, date="2026-04-27", match_id=22581),
    match(NEFC, MFA, 3, 0, date="2026-04-27", match_id=22563),
    match(ORLANDO, NEFC, 1, 1, pens=(4, 2), date="2026-04-28", match_id=22673),
    match(MFA, TRIANGLE, 3, 4, date="2026-04-28", match_id=22620),
]

# ── 2026 MLS NEXT Flex U17, Group H ─────────────────────────────────────
# LA Galaxy drew all three and won all three shootouts: official 6 (0W 0L 3T).
GALAXY = team(5, "LA Galaxy")
WESTON = team(6, "Weston FC")
IFA = team(7, "Intercontinental Football Academy of New England")
WOLVES = team(8, "Michigan Wolves")

GROUP_H = [
    match(GALAXY, WOLVES, 2, 2, pens=(4, 2), date="2026-04-25"),
    match(IFA, WESTON, 0, 3, date="2026-04-25"),
    match(WESTON, GALAXY, 1, 1, pens=(1, 3), date="2026-04-27"),
    match(IFA, WOLVES, 4, 2, date="2026-04-27"),
    match(GALAXY, IFA, 3, 3, pens=(5, 4), date="2026-04-28"),
    match(WOLVES, WESTON, 2, 1, date="2026-04-28"),
]


@pytest.mark.unit
class TestOfficialFlexTables:
    def test_group_c_matches_the_published_table(self):
        table = calculate_standings(GROUP_C)
        assert [(r["team"], r["points"]) for r in table] == [
            ("Orlando City SC", 8),
            ("NEFC", 7),
            ("Triangle United Soccer Association", 3),
            ("Michigan Futbol Academy", 0),
        ]

    def test_a_shootout_is_a_draw_in_the_record_and_not_in_the_points(self):
        # Official columns: Orlando 2W 0L 1T, NEFC 2W 0L 1T. Same record,
        # one point apart — the shootout is the whole difference.
        orlando = row(calculate_standings(GROUP_C), "Orlando City SC")
        nefc = row(calculate_standings(GROUP_C), "NEFC")
        assert (orlando["wins"], orlando["draws"], orlando["losses"]) == (2, 1, 0)
        assert (nefc["wins"], nefc["draws"], nefc["losses"]) == (2, 1, 0)
        assert orlando["points"] - nefc["points"] == 1

    def test_the_row_says_which_way_the_shootout_went(self):
        table = calculate_standings(GROUP_C)
        assert row(table, "Orlando City SC")["shootout_wins"] == 1
        assert row(table, "Orlando City SC")["shootout_losses"] == 0
        assert row(table, "NEFC")["shootout_wins"] == 0
        assert row(table, "NEFC")["shootout_losses"] == 1

    def test_shootout_kicks_are_not_goals(self):
        # Official GF/GA: Orlando 7/2, NEFC 7/1. The 4-2 shootout is nowhere
        # in the goal columns.
        table = calculate_standings(GROUP_C)
        assert (row(table, "Orlando City SC")["goals_for"], row(table, "Orlando City SC")["goals_against"]) == (7, 2)
        assert (row(table, "NEFC")["goals_for"], row(table, "NEFC")["goals_against"]) == (7, 1)

    def test_three_shootout_wins_top_a_group_without_a_regulation_win(self):
        galaxy = row(calculate_standings(GROUP_H), "LA Galaxy")
        assert (galaxy["wins"], galaxy["draws"], galaxy["losses"]) == (0, 3, 0)
        assert galaxy["shootout_wins"] == 3
        assert galaxy["points"] == 6
        assert calculate_standings(GROUP_H)[0]["team"] == "LA Galaxy"

    def test_group_h_matches_the_published_table(self):
        table = calculate_standings(GROUP_H)
        assert {r["team"]: r["points"] for r in table} == {
            "LA Galaxy": 6,
            "Weston FC": 4,
            "Intercontinental Football Academy of New England": 4,
            "Michigan Wolves": 4,
        }


@pytest.mark.unit
class TestTheRuleBelongsToTheCompetition:
    def test_a_league_draw_with_a_shootout_recorded_is_still_a_draw(self):
        # Nothing in League play settles a draw on penalties. If a shootout is
        # ever recorded against a League match, it does not become points.
        table = calculate_standings([match(ORLANDO, NEFC, 1, 1, match_type=LEAGUE, pens=(4, 2))])
        assert row(table, "Orlando City SC")["points"] == 1
        assert row(table, "NEFC")["points"] == 1
        assert row(table, "Orlando City SC")["shootout_wins"] == 0

    def test_a_tournament_shootout_is_progression_not_points(self):
        table = calculate_standings([match(ORLANDO, NEFC, 0, 0, match_type=TOURNAMENT, pens=(5, 4))])
        assert {r["points"] for r in table} == {1}

    def test_the_name_is_not_the_rule(self):
        # A competition called Flex with the flag off scores like League. The
        # flag is the only input — a hardcoded name list is the shape of bug
        # SB-849 removed.
        unflagged_flex = {"id": 5, "name": "Flex", "shootout_points": False}
        table = calculate_standings([match(ORLANDO, NEFC, 1, 1, match_type=unflagged_flex, pens=(4, 2))])
        assert {r["points"] for r in table} == {1}

    def test_a_missing_flag_reads_as_off(self):
        # Rows fetched before the migration, or a stub without the field.
        table = calculate_standings([match(ORLANDO, NEFC, 1, 1, match_type={"id": 5, "name": "Flex"}, pens=(4, 2))])
        assert {r["points"] for r in table} == {1}


@pytest.mark.unit
class TestAbsentShootoutData:
    def test_a_level_flex_match_with_no_shootout_recorded_is_a_plain_draw(self):
        # Absent is not zero. Nobody recorded who won the shootout, so nobody
        # is awarded the extra point — and nobody is charged a shootout loss.
        table = calculate_standings([match(ORLANDO, NEFC, 1, 1)])
        assert {r["points"] for r in table} == {1}
        assert {r["shootout_wins"] for r in table} == {0}
        assert {r["shootout_losses"] for r in table} == {0}
        assert {r["draws"] for r in table} == {1}

    def test_one_side_of_the_shootout_missing_is_absent(self):
        m = match(ORLANDO, NEFC, 1, 1)
        m["home_penalty_score"] = 4
        assert shootout_result(m) is None

    def test_a_level_shootout_decides_nothing(self):
        assert shootout_result(match(ORLANDO, NEFC, 1, 1, pens=(3, 3))) is None

    def test_a_shootout_on_a_match_that_was_not_level_is_ignored(self):
        # Data error: a 2-1 result cannot have gone to penalties. The
        # regulation result stands and the shootout changes nothing.
        table = calculate_standings([match(ORLANDO, NEFC, 2, 1, pens=(0, 3))])
        assert row(table, "Orlando City SC")["points"] == 3
        assert row(table, "NEFC")["points"] == 0


@pytest.mark.unit
class TestHelpers:
    def test_awards_shootout_points_reads_the_flag(self):
        assert awards_shootout_points(match(ORLANDO, NEFC, 1, 1)) is True
        assert awards_shootout_points(match(ORLANDO, NEFC, 1, 1, match_type=LEAGUE)) is False
        assert awards_shootout_points({"match_type": None}) is False
        assert awards_shootout_points({}) is False

    def test_shootout_result_names_the_winner(self):
        assert shootout_result(match(ORLANDO, NEFC, 1, 1, pens=(4, 2))) == "home"
        assert shootout_result(match(ORLANDO, NEFC, 1, 1, pens=(1, 3))) == "away"

    def test_shootout_competitions_lists_the_flagged_ones_present(self):
        mixed = [
            match(ORLANDO, NEFC, 1, 1, match_type=LEAGUE),
            match(ORLANDO, NEFC, 1, 1, pens=(4, 2)),
            match(ORLANDO, NEFC, 1, 1, match_type=TOURNAMENT, pens=(4, 2)),
        ]
        assert shootout_competitions(mixed) == ["Flex"]
        assert shootout_competitions([mixed[0]]) == []
        assert shootout_competitions([]) == []


@pytest.mark.unit
class TestCombinedTable:
    def test_league_and_flex_score_under_their_own_rules_side_by_side(self):
        # The qualifying view sums League and Flex into one table. Orlando
        # draws NEFC 1-1 in League (1 each) and beats them on penalties in
        # Flex (2 to 1). Both must be scored under their own competition's
        # rule in the same pass — this is the hard part of SB-1027.
        combined = [
            match(ORLANDO, NEFC, 1, 1, match_type=LEAGUE, date="2026-03-01"),
            match(ORLANDO, NEFC, 1, 1, pens=(4, 2), date="2026-04-28"),
        ]
        table = calculate_standings(combined)
        orlando, nefc = row(table, "Orlando City SC"), row(table, "NEFC")
        assert (orlando["points"], nefc["points"]) == (3, 2)
        assert (orlando["draws"], nefc["draws"]) == (2, 2)
        assert (orlando["shootout_wins"], nefc["shootout_losses"]) == (1, 1)

    def test_only_team_ids_still_scores_an_outsiders_shootout_for_the_insider(self):
        # NEFC is outside the table; Orlando's shootout win over them still
        # counts for Orlando and NEFC gets no row.
        table = calculate_standings([match(ORLANDO, NEFC, 1, 1, pens=(4, 2))], only_team_ids={ORLANDO["id"]})
        assert [r["team"] for r in table] == ["Orlando City SC"]
        assert table[0]["points"] == 2


@pytest.mark.unit
class TestFormAndExtras:
    def test_form_shows_a_shootout_as_a_draw(self):
        # The official table files it under T. Form does the same; the points
        # column is where the shootout shows.
        form = get_team_form(GROUP_C)
        assert form["Orlando City SC"] == ["W", "W", "D"]
        assert form["NEFC"] == ["W", "W", "D"]

    def test_extras_keep_the_shootout_columns(self):
        table = calculate_standings_with_extras(GROUP_C)
        orlando = row(table, "Orlando City SC")
        assert orlando["shootout_wins"] == 1
        # Before the last match day Orlando and NEFC were level on 6 with NEFC
        # ahead on goal difference. The shootout win is what moved Orlando up.
        assert orlando["position_change"] == 1
        assert row(table, "NEFC")["position_change"] == -1
