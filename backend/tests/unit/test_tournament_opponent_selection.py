"""Unit tests for picking a tournament opponent by id (SB-817).

The Add Match form used to take the opponent as free text, and
`get_or_create_opponent_team` matches names exactly — so a typo minted a
duplicate lightweight team instead of reusing the one already in MT. The form
now sends `opponent_team_id` for a picked team and falls back to
`opponent_name` only when the user explicitly asks to create one.

These tests pin the DAO half of that contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.fixture
def dao():
    from dao.tournament_dao import TournamentDAO

    # Bypass BaseDAO's connection-holder isinstance check — nothing here
    # touches a real database.
    d = TournamentDAO.__new__(TournamentDAO)
    d.connection_holder = MagicMock()
    d.client = MagicMock()
    return d


def _capture_insert(dao):
    """Stub `.insert()` and return the dict it received."""
    captured = {}
    table = MagicMock()

    def insert(data):
        captured["data"] = data
        chain = MagicMock()
        chain.execute.return_value.data = [{"id": 99, **data}]
        return chain

    table.insert.side_effect = insert
    dao.client.table.return_value = table
    return captured


BASE = {
    "tournament_id": 5,
    "our_team_id": 10,
    "match_date": "2026-09-01",
    "age_group_id": 3,
    "season_id": 184,
}


class TestOpponentByIdSkipsNameResolution:
    def test_picked_team_is_used_directly(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(**BASE, opponent_name=None, opponent_team_id=42)

        dao.get_or_create_opponent_team.assert_not_called()
        assert captured["data"]["home_team_id"] == 10
        assert captured["data"]["away_team_id"] == 42

    def test_picked_team_wins_over_a_stale_name(self, dao):
        """A leftover name must never override an explicit selection."""
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(return_value=777)

        dao.create_tournament_match(**BASE, opponent_name="Typo FC", opponent_team_id=42)

        dao.get_or_create_opponent_team.assert_not_called()
        assert captured["data"]["away_team_id"] == 42

    def test_away_side_respects_is_home_false(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        dao.create_tournament_match(**BASE, opponent_name=None, opponent_team_id=42, is_home=False)

        assert captured["data"]["home_team_id"] == 42
        assert captured["data"]["away_team_id"] == 10


class TestOpponentByNameStillWorks:
    def test_name_resolves_through_get_or_create(self, dao):
        captured = _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock(return_value=555)

        dao.create_tournament_match(**BASE, opponent_name="Brand New FC")

        dao.get_or_create_opponent_team.assert_called_once_with("Brand New FC", 3)
        assert captured["data"]["away_team_id"] == 555


class TestOpponentRequired:
    """The deprecated our_team/opponent form still has to name an opponent."""

    def test_neither_id_nor_name_is_rejected(self, dao):
        _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        with pytest.raises(ValueError, match="away_team_id or away_team_name"):
            dao.create_tournament_match(**BASE, opponent_name=None)

        dao.get_or_create_opponent_team.assert_not_called()

    def test_blank_name_is_rejected(self, dao):
        _capture_insert(dao)
        dao.get_or_create_opponent_team = MagicMock()

        with pytest.raises(ValueError, match="away_team_id or away_team_name"):
            dao.create_tournament_match(**BASE, opponent_name="")

        dao.get_or_create_opponent_team.assert_not_called()
