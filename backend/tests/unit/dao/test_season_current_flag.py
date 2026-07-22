"""Unit tests for the admin-set current-season flag (SeasonDAO).

get_current_season prefers seasons.is_current, falling back to the
date-spanning season; set_current_season clears then sets so exactly one
season is current.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.season_dao import SeasonDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _make_dao() -> tuple[SeasonDAO, MagicMock]:
    client_mock = MagicMock()
    dao = SeasonDAO.__new__(SeasonDAO)
    dao.connection_holder = MagicMock()
    dao.client = client_mock
    return dao, client_mock


class TestGetCurrentSeason:
    def test_prefers_is_current_flag(self):
        dao, client = _make_dao()
        # First execute() = the is_current query; return a flagged season.
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": 184, "name": "2026-2027", "is_current": True}]
        )

        season = dao.get_current_season()

        assert season["id"] == 184
        assert season["name"] == "2026-2027"

    def test_falls_back_to_date_when_no_flag(self):
        dao, client = _make_dao()
        # is_current query returns nothing...
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        # ...date-spanning query returns the season for today.
        client.table.return_value.select.return_value.lte.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": 3, "name": "2025-2026", "is_current": False}]
        )

        season = dao.get_current_season()

        assert season["id"] == 3

    def test_returns_none_when_nothing_current(self):
        dao, client = _make_dao()
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        client.table.return_value.select.return_value.lte.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        assert dao.get_current_season() is None


class TestSetCurrentSeason:
    def test_clears_then_sets(self):
        dao, client = _make_dao()
        # get_season_by_id (the final read) returns the target season.
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": 3, "name": "2025-2026", "is_current": True}]
        )

        result = dao.set_current_season(3)

        assert result["id"] == 3
        # Two update() calls: clear every current row, then set the target.
        update_mock = client.table.return_value.update
        assert update_mock.call_count == 2
        cleared = update_mock.call_args_list[0].args[0]
        set_target = update_mock.call_args_list[1].args[0]
        assert cleared == {"is_current": False}
        assert set_target == {"is_current": True}
