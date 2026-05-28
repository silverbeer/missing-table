"""Unit tests for NotificationPreferencesDAO (SB-57).

Uses a mocked Supabase client. The DAO's value is in the merge-with-defaults
logic and the batch-fetch shape — not in the SQL, which the migration's
CHECK constraint and RLS policies already validate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.notification_preferences_dao import NotificationPreferencesDAO
from notifications.preferences import DEFAULT_PREFERENCES

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]


def _make_dao() -> tuple[NotificationPreferencesDAO, MagicMock, MagicMock]:
    """Build a DAO whose `client.table(...)` returns a fluent chainable mock."""
    table_mock = MagicMock()
    client_mock = MagicMock()
    client_mock.table.return_value = table_mock
    connection_holder = MagicMock()
    connection_holder.get_client.return_value = client_mock

    # Bypass BaseDAO's SupabaseConnection isinstance check by constructing
    # the object directly and assigning the fields we need.
    dao = NotificationPreferencesDAO.__new__(NotificationPreferencesDAO)
    dao.connection_holder = connection_holder
    dao.client = client_mock
    return dao, client_mock, table_mock


def _stub_select_returns(table_mock: MagicMock, rows: list[dict]) -> None:
    """Wire up a chain like `.table(T).select(C).eq(...).execute()`."""
    execute_mock = MagicMock()
    execute_mock.data = rows
    table_mock.select.return_value.eq.return_value.execute.return_value = execute_mock
    table_mock.select.return_value.in_.return_value.execute.return_value = execute_mock


class TestGetPreferences:
    def test_returns_defaults_when_no_rows_stored(self):
        dao, _client, table = _make_dao()
        _stub_select_returns(table, [])

        prefs = dao.get_preferences("user-1")

        assert prefs == DEFAULT_PREFERENCES
        # Returns a copy, not the module-level dict reference.
        assert prefs is not DEFAULT_PREFERENCES

    def test_stored_rows_override_defaults(self):
        dao, _client, table = _make_dao()
        _stub_select_returns(
            table,
            [
                {"event_type": "goal", "enabled": False},
                {"event_type": "yellow_card", "enabled": True},
            ],
        )

        prefs = dao.get_preferences("user-1")

        assert prefs["goal"] is False  # overridden
        assert prefs["yellow_card"] is True  # overridden
        assert prefs["kickoff"] is True  # default
        assert prefs["red_card"] is False  # default
        # All known event types are present.
        assert set(prefs.keys()) == set(DEFAULT_PREFERENCES.keys())

    def test_returns_defaults_on_query_error(self):
        dao, _client, table = _make_dao()
        table.select.return_value.eq.return_value.execute.side_effect = RuntimeError(
            "db down"
        )

        prefs = dao.get_preferences("user-1")

        assert prefs == DEFAULT_PREFERENCES


class TestSetPreferences:
    def test_upserts_only_known_event_types(self):
        dao, _client, table = _make_dao()
        upsert_mock = MagicMock()
        upsert_mock.execute.return_value = MagicMock(data=[])
        table.upsert.return_value = upsert_mock
        # Subsequent get_preferences read after the set.
        _stub_select_returns(table, [{"event_type": "goal", "enabled": False}])

        result = dao.set_preferences(
            "user-1", {"goal": False, "not_a_real_event": True}
        )

        # Only goal made it into the upsert payload.
        upsert_args = table.upsert.call_args
        rows = upsert_args.args[0]
        assert len(rows) == 1
        assert rows[0] == {"user_id": "user-1", "event_type": "goal", "enabled": False}
        # on_conflict targets the composite PK.
        assert upsert_args.kwargs.get("on_conflict") == "user_id,event_type"
        # Result reflects the post-upsert read.
        assert result["goal"] is False

    def test_no_rows_no_upsert(self):
        dao, _client, table = _make_dao()
        _stub_select_returns(table, [])

        # All keys unknown → nothing upserted, falls through to a read.
        result = dao.set_preferences("user-1", {"junk": True})

        table.upsert.assert_not_called()
        assert result == DEFAULT_PREFERENCES

    def test_coerces_truthy_values_to_bool(self):
        dao, _client, table = _make_dao()
        table.upsert.return_value.execute.return_value = MagicMock(data=[])
        _stub_select_returns(table, [])

        dao.set_preferences("user-1", {"goal": 1, "kickoff": ""})  # truthy/falsy

        rows = table.upsert.call_args.args[0]
        as_dict = {r["event_type"]: r["enabled"] for r in rows}
        assert as_dict == {"goal": True, "kickoff": False}


class TestGetPreferencesBatch:
    def test_empty_user_list_returns_empty_dict(self):
        dao, _client, table = _make_dao()

        result = dao.get_preferences_batch([])

        assert result == {}
        table.select.assert_not_called()

    def test_fills_defaults_for_users_with_no_rows(self):
        dao, _client, table = _make_dao()
        _stub_select_returns(
            table,
            [
                {"user_id": "u1", "event_type": "goal", "enabled": False},
            ],
        )

        result = dao.get_preferences_batch(["u1", "u2"])

        assert result["u1"]["goal"] is False
        assert result["u1"]["kickoff"] is True  # default
        # u2 has no stored rows → entirely default.
        assert result["u2"] == DEFAULT_PREFERENCES
        # Defensive: returned dicts must include every known event type.
        for prefs in result.values():
            assert set(prefs.keys()) == set(DEFAULT_PREFERENCES.keys())

    def test_returns_defaults_for_all_on_query_error(self):
        dao, _client, table = _make_dao()
        table.select.return_value.in_.return_value.execute.side_effect = (
            RuntimeError("db down")
        )

        result = dao.get_preferences_batch(["u1", "u2"])

        assert result == {"u1": DEFAULT_PREFERENCES, "u2": DEFAULT_PREFERENCES}
