"""Which divisions are worth offering, and in what order the leagues come (SB-1035).

`/api/divisions?league_id=` lists every division a league has ever had. With
U15 / Homegrown / 2026-2027 that offered twelve, of which one has a fixture:
Pathway does not exist at U15, and Florida U15-U19 has sent nothing
(SB-1021). Eleven entries that each yield a blank table is a control promising
data that is not coming.

And the League row sorted by name — Academy, Flex, Homegrown — putting the
competition MT exists for third. The order now lives on `leagues.display_order`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app import divisions_worth_offering, in_display_order
from dao.match_dao import MatchDAO

NORTHEAST = {"id": 1, "name": "Northeast", "league_id": 1}
FLORIDA = {"id": 8, "name": "Florida", "league_id": 1}
NORTHEAST_PATHWAY = {"id": 294, "name": "Northeast (Pro Player Pathway)", "league_id": 1}
HOMEGROWN_DIVISIONS = [FLORIDA, NORTHEAST, NORTHEAST_PATHWAY]


def names(rows: list[dict]) -> list[str]:
    return [r["name"] for r in rows]


@pytest.mark.unit
class TestDivisionsWorthOffering:
    def test_only_divisions_with_fixtures_are_offered(self):
        # 2026-2027 U15 Homegrown: Northeast has 190 fixtures, nothing else has any.
        offered = divisions_worth_offering(HOMEGROWN_DIVISIONS, {1: {"matches": 190, "played": 42}})
        assert names(offered) == ["Northeast"]

    def test_a_division_with_fixtures_but_no_results_is_still_offered(self):
        # Pre-season: scheduled, none played. "No results yet" is not "not
        # played here" — the table is empty, but it is coming.
        offered = divisions_worth_offering(HOMEGROWN_DIVISIONS, {1: {"matches": 19, "played": 0}})
        assert names(offered) == ["Northeast"]
        assert offered[0]["played"] == 0

    def test_each_row_carries_its_counts(self):
        offered = divisions_worth_offering(HOMEGROWN_DIVISIONS, {1: {"matches": 190, "played": 42}})
        assert offered[0]["matches"] == 190
        assert offered[0]["played"] == 42

    def test_nothing_present_offers_nothing(self):
        # Florida U15: divisions exist, fixtures do not. An empty dropdown is
        # the truthful answer, not a list of blank tables.
        assert divisions_worth_offering(HOMEGROWN_DIVISIONS, {}) == []

    def test_a_zero_count_is_absent(self):
        assert divisions_worth_offering(HOMEGROWN_DIVISIONS, {1: {"matches": 0, "played": 0}}) == []

    def test_input_order_is_kept(self):
        counts = {d["id"]: {"matches": 1, "played": 0} for d in HOMEGROWN_DIVISIONS}
        assert names(divisions_worth_offering(HOMEGROWN_DIVISIONS, counts)) == names(HOMEGROWN_DIVISIONS)


HOMEGROWN = {"id": 1, "name": "Homegrown", "display_order": 1}
FLEX = {"id": 290, "name": "Flex", "display_order": 2}
ACADEMY = {"id": 2, "name": "Academy", "display_order": 3}
TSC = {"id": 90, "name": "TSC League 1", "display_order": None}
KICK_FUTSAL = {"id": 34, "name": "Kick Futsal", "display_order": None}


@pytest.mark.unit
class TestLeagueOrder:
    def test_display_order_beats_the_alphabet(self):
        assert names(in_display_order([ACADEMY, FLEX, HOMEGROWN, TSC])) == [
            "Homegrown",
            "Flex",
            "Academy",
            "TSC League 1",
        ]

    def test_unordered_leagues_come_last_by_name(self):
        assert names(in_display_order([TSC, KICK_FUTSAL, HOMEGROWN])) == ["Homegrown", "Kick Futsal", "TSC League 1"]

    def test_a_row_without_the_column_is_treated_as_unordered(self):
        # An API backed by a database that predates the migration.
        assert names(in_display_order([{"id": 90, "name": "TSC League 1"}, HOMEGROWN])) == [
            "Homegrown",
            "TSC League 1",
        ]


# ── MatchDAO.get_divisions_present ───────────────────────────────────


@pytest.fixture(autouse=True)
def no_cached_counts():
    """Same trap as get_leagues_present: cached, and Redis is reachable here."""
    from dao.base_dao import clear_cache

    clear_cache("mt:dao:matches:divisions_present:*")
    yield
    clear_cache("mt:dao:matches:divisions_present:*")


def _dao(match_rows):
    dao = object.__new__(MatchDAO)
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=match_rows)
    client.table.return_value = chain
    dao.client = client
    dao._chain = chain
    return dao


@pytest.mark.unit
class TestDivisionsPresent:
    def test_it_counts_fixtures_and_played_per_division(self):
        dao = _dao(
            [
                {"division_id": 1, "match_status": "completed"},
                {"division_id": 1, "match_status": "scheduled"},
                {"division_id": 1, "match_status": "forfeit"},
                {"division_id": 309, "match_status": "scheduled"},
            ]
        )
        assert dao.get_divisions_present(season_id=184, age_group_id=3) == [
            {"division_id": 1, "matches": 3, "played": 2},
            {"division_id": 309, "matches": 1, "played": 0},
        ]

    def test_a_match_with_no_division_is_not_counted(self):
        dao = _dao([{"division_id": None, "match_status": "completed"}])
        assert dao.get_divisions_present(season_id=184, age_group_id=3) == []

    def test_it_filters_by_season_and_age_group(self):
        dao = _dao([])
        dao.get_divisions_present(season_id=184, age_group_id=3)
        filters = {call.args for call in dao._chain.eq.call_args_list}
        assert ("season_id", 184) in filters
        assert ("age_group_id", 3) in filters
        assert ("is_test", False) in filters

    def test_it_returns_a_list_so_the_cache_cannot_stringify_the_keys(self):
        # JSON has no integer keys; a dict[int, ...] would come back from
        # Redis with string keys and every lookup would miss.
        dao = _dao([{"division_id": 1, "match_status": "completed"}])
        assert isinstance(dao.get_divisions_present(season_id=184, age_group_id=3), list)
