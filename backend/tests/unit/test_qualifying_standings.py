"""The combined qualifying table, and the coverage that has to ship with it (SB-834).

League and Flex together are what qualify a team for the cup, so the standings
need a view that spans them. It is not a standing, though, and the difference is
the point of these tests.

MLS NEXT Flex brackets cut across Homegrown divisions: a Northeast team plays
Flex opponents that are not in the Northeast table. Folding those results in
gives a team's *record* across the competitions that qualify it — not a table
where everyone has played everyone. Per CLAUDE.md a cross-team statistic ships
with its coverage or it does not ship, so every combined response carries how
many of its matches were against teams outside the table.

The competitions combined are read from `match_types.counts_for_qualification`
(SB-849), never named here — the Matches chips, `mt team matches -c qualifying`
and this table must not be able to disagree about what "qualifying" means.
"""

from unittest.mock import MagicMock

import pytest

from dao.match_dao import STANDINGS_ALL, STANDINGS_QUALIFYING, MatchDAO
from dao.standings import (
    calculate_standings,
    count_outside_table_opponents,
    filter_by_match_types,
    filter_matches_involving,
    teams_in_division,
)

# A Homegrown division, a Pathway division under the same league, and a Flex
# bracket. teams.division_id is a team's *home* division — no team's home
# division is ever a Flex bracket, which is the trap SB-835 fell into.
NORTHEAST, PATHWAY, TURNPIKE = 1, 294, 309

LEAGUE = {"id": 1, "name": "League"}
FLEX = {"id": 5, "name": "Flex"}
FRIENDLY = {"id": 3, "name": "Friendly"}


def team(team_id: int, name: str, division_id: int) -> dict:
    return {"id": team_id, "name": name, "division_id": division_id, "club": {"id": team_id, "name": name}}


IFA = team(11, "IFA", NORTHEAST)
BOLTS = team(12, "Boston Bolts", NORTHEAST)
OAKWOOD = team(13, "Oakwood", NORTHEAST)
MONTREAL = team(90, "CF Montreal", PATHWAY)


def match(match_id, home, away, home_score, away_score, match_type, division_id, date="2026-09-05"):
    return {
        "id": match_id,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
        "match_type": match_type,
        "division_id": division_id,
        "match_status": "completed",
        "match_date": date,
    }


# Northeast League: IFA beat the Bolts, Oakwood drew with the Bolts.
# Northeast Flex: IFA beat CF Montreal, who is in a different division and so
# is not in the Northeast table. That match is the whole problem in miniature.
LEAGUE_MATCHES = [
    match(1, IFA, BOLTS, 3, 1, LEAGUE, NORTHEAST, "2026-09-05"),
    match(2, OAKWOOD, BOLTS, 2, 2, LEAGUE, NORTHEAST, "2026-09-12"),
]
FLEX_MATCHES = [
    match(3, IFA, MONTREAL, 2, 0, FLEX, TURNPIKE, "2026-09-20"),
]
FRIENDLY_MATCHES = [
    match(4, IFA, BOLTS, 0, 5, FRIENDLY, None, "2026-09-25"),
]
ALL_MATCHES = LEAGUE_MATCHES + FLEX_MATCHES + FRIENDLY_MATCHES


# ── pure functions ───────────────────────────────────────────────────


@pytest.mark.unit
class TestFilterByMatchTypes:
    def test_none_is_the_pass_through(self):
        # filter_by_match_type (singular) had no way to say "every competition",
        # which is why there was no combined table at all.
        assert filter_by_match_types(ALL_MATCHES, None) == ALL_MATCHES

    def test_a_set_keeps_only_those_competitions(self):
        kept = filter_by_match_types(ALL_MATCHES, {"League", "Flex"})
        assert [m["id"] for m in kept] == [1, 2, 3]

    def test_an_empty_set_keeps_nothing(self):
        # Not the same as None. Nothing flagged means nothing qualifies.
        assert filter_by_match_types(ALL_MATCHES, set()) == []


@pytest.mark.unit
class TestTeamsInDivision:
    def test_the_table_is_built_from_in_division_matches(self):
        assert teams_in_division(ALL_MATCHES, NORTHEAST) == {IFA["id"], BOLTS["id"], OAKWOOD["id"]}

    def test_a_flex_match_does_not_add_a_team_to_the_homegrown_table(self):
        # IFA vs CF Montreal is a Northeast team's match, but it is filed to a
        # Flex bracket, so it does not put CF Montreal in the Northeast table.
        assert MONTREAL["id"] not in teams_in_division(ALL_MATCHES, NORTHEAST)

    def test_a_flex_bracket_has_a_table_of_its_own(self):
        # No team's teams.division_id is ever a Flex bracket. Reading the
        # match's division is the only way this bracket has any teams at all.
        assert teams_in_division(ALL_MATCHES, TURNPIKE) == {IFA["id"], MONTREAL["id"]}

    def test_a_division_nobody_plays_in_is_empty(self):
        assert teams_in_division(LEAGUE_MATCHES, TURNPIKE) == set()


@pytest.mark.unit
class TestMatchesCounted:
    def test_one_side_in_the_table_is_enough(self):
        counted = filter_matches_involving(ALL_MATCHES, {IFA["id"]})
        assert [m["id"] for m in counted] == [1, 3, 4]

    def test_a_match_with_neither_side_is_dropped(self):
        assert filter_matches_involving(FLEX_MATCHES, {BOLTS["id"]}) == []


@pytest.mark.unit
class TestCoverageCounting:
    def test_it_counts_matches_against_teams_outside_the_table(self):
        roster = {IFA["id"], BOLTS["id"], OAKWOOD["id"]}
        against, outsiders = count_outside_table_opponents(ALL_MATCHES, roster)
        assert (against, outsiders) == (1, 1)

    def test_a_table_that_played_only_itself_reports_zero(self):
        roster = {IFA["id"], BOLTS["id"], OAKWOOD["id"]}
        assert count_outside_table_opponents(LEAGUE_MATCHES, roster) == (0, 0)


@pytest.mark.unit
class TestStandingsRestrictedToATable:
    def test_an_outside_opponent_gets_no_row(self):
        roster = {IFA["id"], BOLTS["id"], OAKWOOD["id"]}
        table = calculate_standings(LEAGUE_MATCHES + FLEX_MATCHES, roster)
        assert MONTREAL["name"] not in {row["team"] for row in table}

    def test_but_the_result_still_counts_for_the_team_in_the_table(self):
        roster = {IFA["id"], BOLTS["id"], OAKWOOD["id"]}
        table = calculate_standings(LEAGUE_MATCHES + FLEX_MATCHES, roster)
        ifa = next(row for row in table if row["team"] == IFA["name"])
        # Two wins: the Bolts in League and CF Montreal in Flex.
        assert (ifa["played"], ifa["points"], ifa["goals_for"]) == (2, 6, 5)

    def test_no_restriction_still_tables_everyone(self):
        table = calculate_standings(LEAGUE_MATCHES + FLEX_MATCHES)
        assert MONTREAL["name"] in {row["team"] for row in table}


# ── MatchDAO.get_standings ───────────────────────────────────────────


@pytest.fixture
def dao():
    """A MatchDAO whose only real behaviour is the standings logic under test."""
    instance = MatchDAO.__new__(MatchDAO)
    instance.client = MagicMock()
    instance._fetch_matches_for_standings = MagicMock(return_value=list(ALL_MATCHES))
    instance.qualifying_match_type_names = MagicMock(return_value={"League", "Flex"})
    return instance


@pytest.mark.unit
class TestGetStandings:
    def test_a_single_competition_is_division_filtered_in_the_query(self, dao):
        dao.get_standings(division_id=NORTHEAST, match_type="League")
        assert dao._fetch_matches_for_standings.call_args.args[2] == NORTHEAST

    def test_a_combined_view_is_not(self, dao):
        # A team's Flex matches carry the Flex bracket's division_id, so a
        # database filter on the Homegrown division would drop exactly the
        # matches being combined.
        dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)
        assert dao._fetch_matches_for_standings.call_args.args[2] is None

    def test_a_single_competition_reports_no_outside_matches(self, dao):
        coverage = dao.get_standings(division_id=NORTHEAST, match_type="League")["coverage"]
        assert coverage["matches_vs_outside_table"] == 0
        assert coverage["competitions"] == ["League"]

    def test_qualifying_combines_the_flagged_competitions(self, dao):
        result = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)
        assert result["coverage"]["competitions"] == ["Flex", "League"]
        # League 2 + Flex 1. The friendly is not a qualifying competition.
        assert result["coverage"]["matches_counted"] == 3

    def test_qualifying_states_its_denominator(self, dao):
        coverage = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)["coverage"]
        assert coverage["matches_vs_outside_table"] == 1
        assert coverage["teams_outside_table"] == 1

    def test_the_outside_opponent_is_not_in_the_combined_table(self, dao):
        rows = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)["standings"]
        assert MONTREAL["name"] not in {row["team"] for row in rows}

    def test_the_combined_table_counts_the_flex_result(self, dao):
        rows = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)["standings"]
        ifa = next(row for row in rows if row["team"] == IFA["name"])
        assert (ifa["played"], ifa["points"]) == (2, 6)

    def test_league_alone_does_not_count_the_flex_result(self, dao):
        rows = dao.get_standings(division_id=NORTHEAST, match_type="League")["standings"]
        ifa = next(row for row in rows if row["team"] == IFA["name"])
        assert (ifa["played"], ifa["points"]) == (1, 3)

    def test_qualifying_reads_the_flag_rather_than_a_hardcoded_pair(self, dao):
        """Unflag Flex and the combined view must shrink on its own."""
        dao.qualifying_match_type_names.return_value = {"League"}
        result = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)
        assert result["coverage"]["competitions"] == ["League"]
        assert result["coverage"]["matches_vs_outside_table"] == 0

    def test_all_includes_the_friendly(self, dao):
        result = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_ALL)
        assert result["coverage"]["competitions"] is None
        assert result["coverage"]["matches_counted"] == 4

    def test_a_division_with_no_flex_reports_a_clean_table(self, dao):
        """U13 and U14 play no Flex. Their qualifying view is just League."""
        dao._fetch_matches_for_standings.return_value = list(LEAGUE_MATCHES)
        coverage = dao.get_standings(division_id=NORTHEAST, match_type=STANDINGS_QUALIFYING)["coverage"]
        assert coverage["matches_counted"] == 2
        assert coverage["matches_vs_outside_table"] == 0

    def test_a_combined_view_without_a_division_has_no_outside(self, dao):
        coverage = dao.get_standings(match_type=STANDINGS_QUALIFYING)["coverage"]
        assert coverage["matches_vs_outside_table"] == 0

    def test_a_flex_bracket_has_a_standings_table(self, dao):
        """SB-835: every Flex table came back empty until the division rule was fixed.

        `filter_same_division_matches` required both teams' teams.division_id
        to equal the bracket. No Homegrown team's home division is ever a Flex
        bracket, so 0 of 68 Flex matches survived and the Flex selector in the
        league table produced a blank screen in production.
        """
        rows = dao.get_standings(division_id=TURNPIKE, match_type="Flex")["standings"]
        assert {row["team"] for row in rows} == {IFA["name"], MONTREAL["name"]}

    def test_a_teams_home_division_does_not_decide_where_a_match_counts(self, dao):
        """The 2025-2026 New England U14 case: one team row, several divisions."""
        away_from_home = match(7, IFA, MONTREAL, 1, 0, LEAGUE, NORTHEAST, "2026-10-01")
        away_from_home["away_team"] = {**MONTREAL, "division_id": 999}
        dao._fetch_matches_for_standings.return_value = [*LEAGUE_MATCHES, away_from_home]

        rows = dao.get_standings(division_id=NORTHEAST, match_type="League")["standings"]
        assert MONTREAL["name"] in {row["team"] for row in rows}

    def test_get_league_table_still_returns_just_the_rows(self, dao):
        rows = dao.get_league_table(division_id=NORTHEAST, match_type="League")
        assert isinstance(rows, list)
        assert {row["team"] for row in rows} == {IFA["name"], BOLTS["name"], OAKWOOD["name"]}


@pytest.mark.unit
class TestCompetitionsPresent:
    """SB-834: the client asks which competitions exist rather than hardcoding age ids.

    U13 and U14 play no Flex and U13/U14/U15 have no Pathway divisions. A tab
    that always yields an empty table is the loading skeleton CLAUDE.md warns
    about, and an age-group id list in the frontend rots the first time MLS
    Next moves the boundary.
    """

    @pytest.fixture
    def dao_with_reference(self, dao):
        dao.client.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[
                {"id": 1, "name": "League", "counts_for_qualification": True, "display_order": 1},
                {"id": 5, "name": "Flex", "counts_for_qualification": True, "display_order": 2},
                {"id": 3, "name": "Friendly", "counts_for_qualification": False, "display_order": 4},
            ]
        )
        return dao

    def test_it_lists_only_competitions_actually_played(self, dao_with_reference):
        present = dao_with_reference.get_competitions_present(division_id=NORTHEAST)
        assert [c["name"] for c in present] == ["League", "Flex", "Friendly"]

    def test_a_division_sees_its_teams_flex_matches(self, dao_with_reference):
        """Flex matches carry a Flex bracket id, so a division_id query would miss them."""
        present = dao_with_reference.get_competitions_present(division_id=NORTHEAST)
        flex = next(c for c in present if c["name"] == "Flex")
        assert flex["matches"] == 1

    def test_an_age_group_with_no_flex_gets_no_flex_row(self, dao_with_reference):
        dao_with_reference._fetch_matches_for_standings.return_value = list(LEAGUE_MATCHES)
        present = dao_with_reference.get_competitions_present(division_id=NORTHEAST)
        assert "Flex" not in {c["name"] for c in present}

    def test_rows_carry_the_qualification_flag(self, dao_with_reference):
        present = dao_with_reference.get_competitions_present(division_id=NORTHEAST)
        flags = {c["name"]: c["counts_for_qualification"] for c in present}
        assert flags == {"League": True, "Flex": True, "Friendly": False}

    def test_played_and_scheduled_are_reported_separately(self, dao_with_reference):
        """ "No results yet" is not the same answer as "not played here"."""
        upcoming = match(9, IFA, BOLTS, None, None, FLEX, TURNPIKE, "2027-01-01")
        upcoming["match_status"] = "scheduled"
        dao_with_reference._fetch_matches_for_standings.return_value = [*ALL_MATCHES, upcoming]

        present = dao_with_reference.get_competitions_present(division_id=NORTHEAST)
        flex = next(c for c in present if c["name"] == "Flex")
        assert (flex["matches"], flex["played"]) == (2, 1)

    def test_in_division_identifies_the_divisions_own_competition(self, dao_with_reference):
        """Northeast's own competition is League; its Flex matches sit under a Flex bracket."""
        present = {c["name"]: c for c in dao_with_reference.get_competitions_present(division_id=NORTHEAST)}
        assert present["League"]["in_division"] == 2
        assert present["Flex"]["in_division"] == 0

    def test_a_flex_bracket_owns_flex(self, dao_with_reference):
        present = {c["name"]: c for c in dao_with_reference.get_competitions_present(division_id=TURNPIKE)}
        assert present["Flex"]["in_division"] == 1

    def test_no_matches_at_all_is_an_empty_list_not_an_error(self, dao_with_reference):
        dao_with_reference._fetch_matches_for_standings.return_value = []
        assert dao_with_reference.get_competitions_present(division_id=NORTHEAST) == []
