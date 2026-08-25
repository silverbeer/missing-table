"""Division name resolution is scoped to a league (SB-830).

Division names are unique per league, not globally — `divisions` is
UNIQUE (name, league_id). The 2026-2027 MLS Next feeds make that concrete:
"Florida", "Frontier", "Northwest" and "Southeast" are each a Homegrown
division AND a separate MLS NEXT Flex one.

An unscoped lookup returns whichever row the database hands back first, so a
Flex match lands in a Homegrown standings table with nothing to show that it
went wrong. That is the failure this suite exists to prevent.
"""

from unittest.mock import MagicMock

import pytest

HOMEGROWN_FLORIDA = {"id": 127, "name": "Florida", "league_id": 1}
FLEX_FLORIDA = {"id": 300, "name": "Florida", "league_id": 40}


def _league_dao(rows):
    from dao.league_dao import LeagueDAO

    dao = object.__new__(LeagueDAO)
    dao.connection_holder = MagicMock()
    client = MagicMock()
    table = MagicMock()
    table.select.return_value = table
    table.ilike.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=rows)
    client.table.return_value = table
    dao.client = client
    dao._table = table
    return dao


@pytest.mark.unit
class TestGetDivisionByName:
    def test_scoped_lookup_filters_on_league_id(self):
        dao = _league_dao([HOMEGROWN_FLORIDA])
        assert dao.get_division_by_name("Florida", league_id=1)["id"] == 127
        dao._table.eq.assert_called_once_with("league_id", 1)

    def test_unscoped_lookup_does_not_filter(self):
        dao = _league_dao([HOMEGROWN_FLORIDA])
        assert dao.get_division_by_name("Florida")["id"] == 127
        dao._table.eq.assert_not_called()

    def test_an_ambiguous_name_refuses_to_guess(self):
        # Both Florida divisions come back. Picking one silently is how a Flex
        # result would be counted in the Homegrown table.
        dao = _league_dao([HOMEGROWN_FLORIDA, FLEX_FLORIDA])
        assert dao.get_division_by_name("Florida") is None

    def test_unknown_division_is_none(self):
        dao = _league_dao([])
        assert dao.get_division_by_name("Nowhere", league_id=1) is None

    def test_a_query_error_is_none_not_an_exception(self):
        # Callers treat None as "unresolved" and report it; an exception here
        # would be indistinguishable from the resolution failures we want to
        # surface by name.
        dao = _league_dao([])
        dao._table.execute.side_effect = RuntimeError("connection reset")
        assert dao.get_division_by_name("Florida", league_id=1) is None


@pytest.mark.unit
class TestGetLeagueByName:
    def test_resolves_the_feed_competition_name(self):
        from dao.league_dao import LeagueDAO

        dao = object.__new__(LeagueDAO)
        dao.connection_holder = MagicMock()
        client = MagicMock()
        table = MagicMock()
        table.select.return_value = table
        table.ilike.return_value = table
        table.limit.return_value = table
        table.execute.return_value = MagicMock(data=[{"id": 1, "name": "Homegrown"}])
        client.table.return_value = table
        dao.client = client

        assert dao.get_league_by_name("Homegrown")["id"] == 1
        table.ilike.assert_called_once_with("name", "Homegrown")

    def test_unknown_league_is_none(self):
        dao = _league_dao([])
        assert dao.get_league_by_name("Not A League") is None
