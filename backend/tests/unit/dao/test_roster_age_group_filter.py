"""Unit tests for the SB-68 age_group filter on roster queries.

Mocks the Supabase client to assert that:
  - When `age_group_id` is None, the query has only team + season filters
    (no behavior change vs. pre-SB-68).
  - When `age_group_id` is set, the query adds a strict `.eq("age_group_id", N)`
    filter.

Covers both DAOs that the API exposes:
  - RosterDAO.get_team_roster   → `players` table
  - PlayerDAO.get_team_players  → `player_team_history` table
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.player_dao import PlayerDAO
from dao.roster_dao import RosterDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _build_dao(cls):
    """Build a DAO whose `client.table(...)` is a chainable mock.

    Bypasses BaseDAO's SupabaseConnection isinstance check by setting the
    fields directly.
    """
    client_mock = MagicMock()
    holder = MagicMock()
    holder.get_client.return_value = client_mock

    dao = cls.__new__(cls)
    dao.connection_holder = holder
    dao.client = client_mock
    return dao, client_mock


# ---------------------------------------------------------------------------
# RosterDAO.get_team_roster
# ---------------------------------------------------------------------------


class TestGetTeamRosterFilter:
    def _setup_query_chain(self, client_mock, returned_rows):
        """Wire the chainable mock so .eq().eq().eq().[.eq()].order().execute()
        returns `returned_rows` regardless of intermediate calls."""
        execute_mock = MagicMock()
        execute_mock.data = returned_rows
        order_mock = MagicMock()
        order_mock.execute.return_value = execute_mock
        eq_mock = MagicMock()
        eq_mock.order.return_value = order_mock
        eq_mock.eq.return_value = eq_mock
        client_mock.table.return_value.select.return_value.eq.return_value = eq_mock

    def test_no_age_group_filter_when_arg_is_none(self):
        dao, client = _build_dao(RosterDAO)
        self._setup_query_chain(client, [])

        dao.get_team_roster(team_id=10, season_id=3, age_group_id=None)

        # The chain of .eq() calls on the post-select mock should NOT include
        # an age_group_id eq.
        eq_chain = client.table.return_value.select.return_value
        # First eq: team_id, returns the inner mock; subsequent eq's are on
        # that inner mock.
        eq_chain.eq.assert_called_with("team_id", 10)
        inner = eq_chain.eq.return_value
        eq_calls = [c.args for c in inner.eq.call_args_list]
        assert ("age_group_id", None) not in eq_calls
        # Sanity: season_id and is_active are still applied.
        assert ("season_id", 3) in eq_calls
        assert ("is_active", True) in eq_calls

    def test_age_group_filter_when_arg_is_set(self):
        dao, client = _build_dao(RosterDAO)
        self._setup_query_chain(client, [])

        dao.get_team_roster(team_id=10, season_id=3, age_group_id=2)

        eq_chain = client.table.return_value.select.return_value
        inner = eq_chain.eq.return_value
        eq_calls = [c.args for c in inner.eq.call_args_list]
        assert ("age_group_id", 2) in eq_calls

    def test_returns_empty_list_when_query_fails(self):
        dao, client = _build_dao(RosterDAO)
        client.table.return_value.select.return_value.eq.side_effect = RuntimeError(
            "db down"
        )

        result = dao.get_team_roster(team_id=10, season_id=3, age_group_id=2)
        assert result == []


# ---------------------------------------------------------------------------
# PlayerDAO.get_team_players
# ---------------------------------------------------------------------------


class TestGetTeamPlayersFilter:
    def _setup_query_chain(self, client_mock, returned_rows):
        execute_mock = MagicMock()
        execute_mock.data = returned_rows
        eq_mock = MagicMock()
        eq_mock.execute.return_value = execute_mock
        eq_mock.eq.return_value = eq_mock
        client_mock.table.return_value.select.return_value.eq.return_value = eq_mock

    def test_no_age_group_filter_when_arg_is_none(self):
        dao, client = _build_dao(PlayerDAO)
        self._setup_query_chain(client, [])

        dao.get_team_players(team_id=19, age_group_id=None)

        eq_chain = client.table.return_value.select.return_value
        eq_chain.eq.assert_called_with("team_id", 19)
        inner = eq_chain.eq.return_value
        eq_calls = [c.args for c in inner.eq.call_args_list]
        assert ("age_group_id", None) not in eq_calls
        assert ("is_current", True) in eq_calls

    def test_age_group_filter_when_arg_is_set(self):
        dao, client = _build_dao(PlayerDAO)
        self._setup_query_chain(client, [])

        dao.get_team_players(team_id=19, age_group_id=3)

        eq_chain = client.table.return_value.select.return_value
        inner = eq_chain.eq.return_value
        eq_calls = [c.args for c in inner.eq.call_args_list]
        assert ("age_group_id", 3) in eq_calls

    def test_returns_empty_list_when_query_fails(self):
        dao, client = _build_dao(PlayerDAO)
        client.table.return_value.select.return_value.eq.side_effect = RuntimeError(
            "boom"
        )

        result = dao.get_team_players(team_id=19, age_group_id=3)
        assert result == []
