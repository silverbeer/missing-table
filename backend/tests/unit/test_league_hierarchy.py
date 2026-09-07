"""Division → Competition → Conference (SB-1039).

The official MLS NEXT standings are organised Division (Homegrown, Academy) →
tab (League, MLS NEXT Flex) → Conference. MT held Flex as a third league
beside the other two. Now a league can name its parent and the competition
its conferences are the tables of, and three things read that:

- which competitions a division plays (across its child leagues),
- whose conferences to offer for a competition (a child league's, for Flex),
- which leagues are divisions at all (those without a parent — the client's
  side, tested in the frontend spec).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app import league_for_competition
from dao.match_dao import MatchDAO

LEAGUE, FLEX = 1, 5
HOMEGROWN = {"id": 1, "name": "Homegrown", "parent_league_id": None, "match_type_id": LEAGUE}
ACADEMY = {"id": 2, "name": "Academy", "parent_league_id": None, "match_type_id": LEAGUE}
FLEX_LEAGUE = {"id": 290, "name": "Flex", "parent_league_id": 1, "match_type_id": FLEX}
TSC = {"id": 90, "name": "TSC League 1"}
LEAGUES = [HOMEGROWN, ACADEMY, FLEX_LEAGUE, TSC]


@pytest.mark.unit
class TestLeagueForCompetition:
    def test_flex_under_homegrown_offers_the_flex_conferences(self):
        assert league_for_competition(LEAGUES, 1, FLEX) == 290

    def test_league_stays_with_the_division_itself(self):
        assert league_for_competition(LEAGUES, 1, LEAGUE) == 1

    def test_no_competition_is_the_division_itself(self):
        # The combined view, or no filter at all.
        assert league_for_competition(LEAGUES, 1, None) == 1

    def test_a_competition_no_child_claims_is_the_division_itself(self):
        assert league_for_competition(LEAGUES, 1, 99) == 1

    def test_a_child_of_another_division_is_not_borrowed(self):
        # Academy + Flex: Academy has no Flex; the Flex league belongs to Homegrown.
        assert league_for_competition(LEAGUES, 2, FLEX) == 2

    def test_rows_without_the_columns_are_harmless(self):
        assert league_for_competition([TSC], 90, FLEX) == 90


# ── MatchDAO: competitions across a league family ────────────────────


@pytest.fixture(autouse=True)
def no_cached_competitions():
    from dao.base_dao import clear_cache

    clear_cache("mt:dao:matches:competitions:*")
    yield
    clear_cache("mt:dao:matches:competitions:*")


NORTHEAST, TURNPIKE, ACADEMY_NE = 1, 309, 7
DIVISIONS = [
    {"id": NORTHEAST, "league_id": 1},
    {"id": TURNPIKE, "league_id": 290},
    {"id": ACADEMY_NE, "league_id": 2},
]
LEAGUE_ROWS = [
    {"id": 1, "parent_league_id": None},
    {"id": 290, "parent_league_id": 1},
    {"id": 2, "parent_league_id": None},
]
MATCH_TYPES = [
    {"id": LEAGUE, "name": "League", "counts_for_qualification": True, "has_standings": True, "display_order": 1},
    {"id": FLEX, "name": "Flex", "counts_for_qualification": True, "has_standings": True, "display_order": 2},
]


def team(team_id):
    return {"id": team_id, "name": f"T{team_id}"}


def match(match_id, division_id, type_id, name):
    return {
        "id": match_id,
        "division_id": division_id,
        "match_type": {"id": type_id, "name": name},
        "home_team": team(10 + match_id),
        "away_team": team(20 + match_id),
        "home_score": None,
        "away_score": None,
        "match_status": "scheduled",
    }


MATCHES = [
    match(1, NORTHEAST, LEAGUE, "League"),
    match(2, NORTHEAST, LEAGUE, "League"),
    match(3, TURNPIKE, FLEX, "Flex"),
    match(4, ACADEMY_NE, LEAGUE, "League"),
]


def _dao():
    dao = object.__new__(MatchDAO)
    client = MagicMock()

    def table(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        data = {"leagues": LEAGUE_ROWS, "divisions": DIVISIONS, "match_types": MATCH_TYPES}[name]
        chain.execute.return_value = MagicMock(data=data)
        return chain

    client.table.side_effect = table
    dao.client = client
    dao._fetch_matches_for_standings = MagicMock(return_value=MATCHES)
    return dao


@pytest.mark.unit
class TestCompetitionsForALeague:
    def test_a_division_plays_its_own_and_its_childrens_competitions(self):
        present = {c["name"]: c for c in _dao().get_competitions_present(season_id=184, age_group_id=3, league_id=1)}
        assert set(present) == {"League", "Flex"}
        assert present["League"]["matches"] == 2
        assert present["Flex"]["matches"] == 1

    def test_in_division_marks_the_divisions_own_competition(self):
        # Two League matches are filed to Northeast, a Homegrown conference;
        # the Flex match is filed to Turnpike, a child league's. So Homegrown
        # opens on League, without anyone looking the league's name up.
        present = {c["name"]: c for c in _dao().get_competitions_present(season_id=184, age_group_id=3, league_id=1)}
        assert present["League"]["in_division"] == 2
        assert present["Flex"]["in_division"] == 0

    def test_another_division_sees_only_its_own(self):
        present = _dao().get_competitions_present(season_id=184, age_group_id=3, league_id=2)
        assert [c["name"] for c in present] == ["League"]
        assert present[0]["matches"] == 1

    def test_a_division_is_scoped_by_the_conference_when_both_are_given(self):
        # division_id wins: the conference's teams, as before (SB-834).
        dao = _dao()
        present = {c["name"] for c in dao.get_competitions_present(season_id=184, age_group_id=3, division_id=TURNPIKE)}
        assert present == {"Flex"}
