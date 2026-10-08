"""Unit tests for ApnsDeviceDAO and the shared follower-user resolution (SB-1236).

Mocked Supabase client, same approach as test_notification_preferences_dao.py:
these pin the query shapes and the swallow-and-log contract, not the SQL.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.apns_device_dao import ApnsDeviceDAO
from dao.bracket_follow_dao import BracketFollowDAO
from dao.team_follow_dao import TeamFollowDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]

TOKEN = "ab" * 32


def _make(cls):
    """DAO instance with a MagicMock client, bypassing BaseDAO's isinstance check."""
    client = MagicMock()
    dao = cls.__new__(cls)
    dao.connection_holder = MagicMock()
    dao.client = client
    return dao, client


def _result(rows):
    res = MagicMock()
    res.data = rows
    return res


class TestUpsert:
    def test_upserts_on_device_token_and_returns_row(self):
        dao, client = _make(ApnsDeviceDAO)
        row = {"id": "dev-1", "user_id": "u-2", "device_token": TOKEN}
        client.table.return_value.upsert.return_value.execute.return_value = _result([row])

        out = dao.upsert("u-2", TOKEN, "production", device_label="Tom's iPhone", app_version="1.0 (3)")

        assert out == row
        client.table.assert_called_with("apns_devices")
        payload = client.table.return_value.upsert.call_args.args[0]
        assert client.table.return_value.upsert.call_args.kwargs == {"on_conflict": "device_token"}
        # Re-registration moves the token to the caller and touches last_seen.
        assert payload["user_id"] == "u-2"
        assert payload["device_token"] == TOKEN
        assert payload["environment"] == "production"
        assert payload["device_label"] == "Tom's iPhone"
        assert payload["app_version"] == "1.0 (3)"
        assert "last_seen_at" in payload
        # Never resets created_at/id; bundle_id left to the column default.
        assert "created_at" not in payload
        assert "id" not in payload
        assert "bundle_id" not in payload

    def test_explicit_bundle_id_is_written(self):
        dao, client = _make(ApnsDeviceDAO)
        client.table.return_value.upsert.return_value.execute.return_value = _result([{"id": "d"}])
        dao.upsert("u-1", TOKEN, "sandbox", bundle_id="com.missingtable.dev")
        assert client.table.return_value.upsert.call_args.args[0]["bundle_id"] == "com.missingtable.dev"

    def test_db_error_returns_none(self):
        dao, client = _make(ApnsDeviceDAO)
        client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("down")
        assert dao.upsert("u-1", TOKEN, "sandbox") is None


class TestList:
    def test_list_by_user_never_selects_the_token(self):
        dao, client = _make(ApnsDeviceDAO)
        chain = client.table.return_value.select.return_value.eq.return_value.order.return_value
        chain.execute.return_value = _result([{"id": "d"}])

        assert dao.list_by_user("u-1") == [{"id": "d"}]
        columns = client.table.return_value.select.call_args.args[0]
        assert "device_token" not in columns
        client.table.return_value.select.return_value.eq.assert_called_with("user_id", "u-1")

    def test_list_for_user_ids_selects_send_columns(self):
        dao, client = _make(ApnsDeviceDAO)
        rows = [{"id": "d1", "user_id": "u-1", "device_token": TOKEN, "environment": "sandbox"}]
        client.table.return_value.select.return_value.in_.return_value.execute.return_value = _result(rows)

        assert dao.list_for_user_ids(["u-1", "u-2"]) == rows
        columns = client.table.return_value.select.call_args.args[0]
        for col in ("id", "user_id", "device_token", "environment", "bundle_id"):
            assert col in columns
        client.table.return_value.select.return_value.in_.assert_called_with("user_id", ["u-1", "u-2"])

    def test_list_for_no_users_skips_the_query(self):
        dao, client = _make(ApnsDeviceDAO)
        assert dao.list_for_user_ids([]) == []
        client.table.assert_not_called()

    def test_list_errors_return_empty(self):
        dao, client = _make(ApnsDeviceDAO)
        client.table.side_effect = RuntimeError("down")
        assert dao.list_by_user("u-1") == []
        assert dao.list_for_user_ids(["u-1"]) == []


class TestDelete:
    def test_delete_for_user_is_scoped_to_the_owner(self):
        dao, client = _make(ApnsDeviceDAO)
        eq1 = client.table.return_value.delete.return_value.eq
        eq1.return_value.eq.return_value.execute.return_value = _result([{"id": "d"}])

        assert dao.delete_for_user("u-1", "d") is True
        eq1.assert_called_with("id", "d")
        eq1.return_value.eq.assert_called_with("user_id", "u-1")

    def test_delete_for_user_returns_false_when_nothing_matched(self):
        dao, client = _make(ApnsDeviceDAO)
        eq1 = client.table.return_value.delete.return_value.eq
        eq1.return_value.eq.return_value.execute.return_value = _result([])
        assert dao.delete_for_user("u-other", "d") is False

    def test_delete_by_token(self):
        dao, client = _make(ApnsDeviceDAO)
        eq = client.table.return_value.delete.return_value.eq
        eq.return_value.execute.return_value = _result([{"id": "d"}])
        assert dao.delete_by_token(TOKEN) is True
        eq.assert_called_with("device_token", TOKEN)

    def test_delete_errors_return_false(self):
        dao, client = _make(ApnsDeviceDAO)
        client.table.side_effect = RuntimeError("down")
        assert dao.delete_for_user("u-1", "d") is False
        assert dao.delete_by_token(TOKEN) is False


class TestTeamFollowerUserIds:
    def test_distinct_users_following_any_team(self):
        dao, client = _make(TeamFollowDAO)
        client.table.return_value.select.return_value.in_.return_value.execute.return_value = _result(
            [{"user_id": "u-1"}, {"user_id": "u-1"}, {"user_id": "u-2"}, {"user_id": None}]
        )
        assert sorted(dao.list_user_ids_for_team_ids([10, 20])) == ["u-1", "u-2"]
        client.table.assert_called_with("user_team_follows")
        client.table.return_value.select.return_value.in_.assert_called_with("team_id", [10, 20])

    def test_no_teams_skips_the_query(self):
        dao, client = _make(TeamFollowDAO)
        assert dao.list_user_ids_for_team_ids([]) == []
        client.table.assert_not_called()

    def test_error_returns_empty(self):
        dao, client = _make(TeamFollowDAO)
        client.table.side_effect = RuntimeError("down")
        assert dao.list_user_ids_for_team_ids([10]) == []

    def test_web_subscriptions_fanout_still_uses_two_queries(self):
        """The refactor must not change the web fan-out's result."""
        dao, client = _make(TeamFollowDAO)
        follows = MagicMock()
        follows.select.return_value.in_.return_value.execute.return_value = _result([{"user_id": "u-1"}])
        subs = MagicMock()
        sub_rows = [
            {"id": "s1", "user_id": "u-1", "endpoint": "e1", "p256dh_key": "k", "auth_key": "a"},
            {"id": "s1", "user_id": "u-1", "endpoint": "e1", "p256dh_key": "k", "auth_key": "a"},
        ]
        subs.select.return_value.in_.return_value.execute.return_value = _result(sub_rows)
        client.table.side_effect = lambda name: {"user_team_follows": follows, "push_subscriptions": subs}[name]

        assert dao.list_subscriptions_for_team_ids([10]) == [sub_rows[0]]
        subs.select.return_value.in_.assert_called_with("user_id", ["u-1"])


class TestBracketFollowerUserIds:
    def test_distinct_users_following_the_bracket(self):
        dao, client = _make(BracketFollowDAO)
        chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value
        chain.execute.return_value = _result([{"user_id": "u-1"}, {"user_id": "u-1"}])
        assert dao.list_user_ids_for_bracket(7, "Bracket A", 3) == ["u-1"]
        client.table.assert_called_with("user_bracket_follows")

    def test_error_returns_empty(self):
        dao, client = _make(BracketFollowDAO)
        client.table.side_effect = RuntimeError("down")
        assert dao.list_user_ids_for_bracket(7, "Bracket A", 3) == []
