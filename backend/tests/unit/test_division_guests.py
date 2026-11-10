"""Guests: teams that play a table's fixtures without being in the table (SB-1598).

The official U15 New England Flex table has no CF Montreal row, yet every other
team's line includes its match against them. So hiding a guest must remove a row
and must not remove a result.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dao.match_dao import STANDINGS_QUALIFYING, MatchDAO

NEW_ENGLAND = 304
ACADEMY_NEW_ENGLAND = 7
SEASON, U15 = 3, 2
FLEX = {"id": 5, "name": "Flex"}

BAYSIDE = {"id": 1, "name": "Bayside FC"}
NEFC = {"id": 2, "name": "NEFC"}
MONTREAL = {"id": 898, "name": "CF Montreal"}


def _match(match_id, home, away, home_score=1, away_score=0, status="completed"):
    return {
        "id": match_id,
        "match_date": f"2026-09-{match_id:02d}",
        "division_id": NEW_ENGLAND,
        "match_status": status,
        "match_type": FLEX,
        "home_team": home,
        "away_team": away,
        "home_score": home_score,
        "away_score": away_score,
    }


MATCHES = [
    _match(1, BAYSIDE, NEFC, 2, 0),
    _match(2, MONTREAL, BAYSIDE, 0, 0),
    _match(3, MONTREAL, NEFC, 1, 2),
]


def _dao(guests):
    instance = MatchDAO.__new__(MatchDAO)
    instance.client = MagicMock()
    instance._fetch_matches_for_standings = MagicMock(return_value=list(MATCHES))
    instance.qualifying_match_type_names = MagicMock(return_value={"League", "Flex"})
    instance._guest_team_ids = MagicMock(return_value=set(guests))
    return instance


def _table(dao, match_type="Flex"):
    result = dao.get_standings(SEASON, U15, NEW_ENGLAND, match_type)
    return {row["team"]: row for row in result["standings"]}


@pytest.mark.unit
class TestGuestsInStandings:
    def test_a_table_with_no_guests_is_unchanged(self):
        assert set(_table(_dao([]))) == {"Bayside FC", "NEFC", "CF Montreal"}

    def test_a_guest_has_no_row(self):
        assert "CF Montreal" not in _table(_dao([MONTREAL["id"]]))

    def test_results_against_a_guest_still_count(self):
        table = _table(_dao([MONTREAL["id"]]))
        assert (table["Bayside FC"]["played"], table["Bayside FC"]["wins"], table["Bayside FC"]["draws"]) == (2, 1, 1)
        assert (table["NEFC"]["played"], table["NEFC"]["wins"], table["NEFC"]["losses"]) == (2, 1, 1)

    def test_the_combined_view_hides_the_guest_too(self):
        table = _table(_dao([MONTREAL["id"]]), STANDINGS_QUALIFYING)
        assert "CF Montreal" not in table
        assert table["NEFC"]["played"] == 2

    def test_guests_are_looked_up_for_this_table(self):
        dao = _dao([])
        _table(dao)
        dao._guest_team_ids.assert_called_once_with(SEASON, U15, NEW_ENGLAND)


@pytest.mark.unit
class TestGuestLookup:
    @staticmethod
    def _dao_reading(result=None, error=None):
        instance = MatchDAO.__new__(MatchDAO)
        instance.client = MagicMock()
        execute = instance.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value
        execute.execute.side_effect = error
        execute.execute.return_value = MagicMock(data=result)
        return instance

    def test_reads_the_team_ids(self):
        assert self._dao_reading([{"team_id": 898}])._guest_team_ids(SEASON, U15, NEW_ENGLAND) == {898}

    def test_a_query_that_is_not_one_table_has_no_guests(self):
        dao = self._dao_reading([{"team_id": 898}])
        assert dao._guest_team_ids(SEASON, None, NEW_ENGLAND) == set()
        dao.client.table.assert_not_called()

    def test_a_failed_read_still_serves_standings(self):
        dao = self._dao_reading(error=RuntimeError("relation does not exist"))
        assert dao._guest_team_ids(SEASON, U15, NEW_ENGLAND) == set()


DIVISIONS = [
    {"id": ACADEMY_NEW_ENGLAND, "name": "New England", "leagues": {"name": "Academy"}},
    {"id": NEW_ENGLAND, "name": "New England", "leagues": {"name": "Flex"}},
]
runner = CliRunner()


@pytest.mark.unit
class TestGuestCommand:
    @staticmethod
    def _invoke(args, guests=()):
        import mt_cli

        client = MagicMock()
        client.get_divisions.return_value = DIVISIONS
        client.list_division_guests.return_value = list(guests)
        with (
            patch.object(mt_cli, "get_client", return_value=(client, None)),
            patch.object(mt_cli, "resolve_team", return_value=MONTREAL),
            patch.object(mt_cli, "_resolve_age_group_id", return_value=U15),
            patch.object(mt_cli, "_resolve_season_id", return_value=SEASON),
        ):
            return runner.invoke(mt_cli.app, ["team", "guest", *args]), client

    def test_add_defaults_to_the_flex_conference_not_the_academy_one(self):
        result, client = self._invoke(["add", "CF Montreal", "-a", "U15", "-d", "New England", "-r", "not a member"])
        assert result.exit_code == 0, result.output
        client.add_division_guest.assert_called_once_with(898, NEW_ENGLAND, U15, SEASON, "not a member")

    def test_add_refuses_a_division_it_cannot_place(self):
        result, client = self._invoke(["add", "CF Montreal", "-a", "U15", "-d", "Nowhere", "-r", "x"])
        assert result.exit_code == 1
        client.add_division_guest.assert_not_called()

    def test_remove_deletes_the_matching_guest(self):
        guests = [{"id": 11, "team_id": 898, "division_id": NEW_ENGLAND}]
        result, client = self._invoke(["remove", "CF Montreal", "-a", "U15", "-d", "New England"], guests)
        assert result.exit_code == 0, result.output
        client.remove_division_guest.assert_called_once_with(11)

    def test_remove_says_so_when_there_is_nothing_to_remove(self):
        result, client = self._invoke(["remove", "CF Montreal", "-a", "U15", "-d", "New England"])
        assert result.exit_code == 1
        client.remove_division_guest.assert_not_called()
