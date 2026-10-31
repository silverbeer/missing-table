"""Unit tests for FcmDeviceDAO (SB-1463).

Mocked Supabase client, same approach as test_apns_device_dao.py: these pin
the query shapes and the swallow-and-log contract, not the SQL.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dao.fcm_device_dao import FcmDeviceDAO

pytestmark = [pytest.mark.unit, pytest.mark.backend, pytest.mark.dao]

FID = "cJx1Yk2zQ9-abc_DEF0123"


def _make():
    """DAO instance with a MagicMock client, bypassing BaseDAO's isinstance check."""
    client = MagicMock()
    dao = FcmDeviceDAO.__new__(FcmDeviceDAO)
    dao.connection_holder = MagicMock()
    dao.client = client
    return dao, client


def _result(rows):
    res = MagicMock()
    res.data = rows
    return res


class TestUpsert:
    def test_upserts_on_fid_and_returns_row(self):
        dao, client = _make()
        row = {"id": "dev-1", "user_id": "u-2", "fid": FID}
        client.table.return_value.upsert.return_value.execute.return_value = _result([row])

        out = dao.upsert("u-2", FID, device_label="Pixel 9", app_version="0.2.18")

        assert out == row
        client.table.assert_called_with("fcm_devices")
        payload = client.table.return_value.upsert.call_args.args[0]
        assert client.table.return_value.upsert.call_args.kwargs == {"on_conflict": "fid"}
        # Re-registration moves the fid to the caller and touches last_seen.
        assert payload["user_id"] == "u-2"
        assert payload["fid"] == FID
        assert payload["device_label"] == "Pixel 9"
        assert payload["app_version"] == "0.2.18"
        assert "last_seen_at" in payload
        # Never resets created_at/id.
        assert "created_at" not in payload
        assert "id" not in payload

    def test_omitted_metadata_is_not_nulled(self):
        """Re-registering without label/version must keep the stored values."""
        dao, client = _make()
        client.table.return_value.upsert.return_value.execute.return_value = _result([{"id": "d"}])
        dao.upsert("u-1", FID)
        payload = client.table.return_value.upsert.call_args.args[0]
        assert "device_label" not in payload
        assert "app_version" not in payload
        assert set(payload) == {"user_id", "fid", "last_seen_at"}

    def test_db_error_returns_none(self):
        dao, client = _make()
        client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("down")
        assert dao.upsert("u-1", FID) is None


class TestList:
    def test_list_by_user_never_selects_the_fid(self):
        dao, client = _make()
        chain = client.table.return_value.select.return_value.eq.return_value.order.return_value
        chain.execute.return_value = _result([{"id": "d"}])

        assert dao.list_by_user("u-1") == [{"id": "d"}]
        columns = [c.strip() for c in client.table.return_value.select.call_args.args[0].split(",")]
        assert "fid" not in columns
        client.table.return_value.select.return_value.eq.assert_called_with("user_id", "u-1")

    def test_list_for_user_ids_selects_send_columns(self):
        dao, client = _make()
        rows = [{"id": "d1", "user_id": "u-1", "fid": FID}]
        client.table.return_value.select.return_value.in_.return_value.execute.return_value = _result(rows)

        assert dao.list_for_user_ids(["u-1", "u-2"]) == rows
        columns = [c.strip() for c in client.table.return_value.select.call_args.args[0].split(",")]
        for col in ("id", "user_id", "fid"):
            assert col in columns
        client.table.return_value.select.return_value.in_.assert_called_with("user_id", ["u-1", "u-2"])

    def test_list_for_no_users_skips_the_query(self):
        dao, client = _make()
        assert dao.list_for_user_ids([]) == []
        client.table.assert_not_called()

    def test_list_errors_return_empty(self):
        dao, client = _make()
        client.table.side_effect = RuntimeError("down")
        assert dao.list_by_user("u-1") == []
        assert dao.list_for_user_ids(["u-1"]) == []


class TestDelete:
    def test_delete_for_user_is_scoped_to_the_owner(self):
        dao, client = _make()
        eq1 = client.table.return_value.delete.return_value.eq
        eq1.return_value.eq.return_value.execute.return_value = _result([{"id": "d"}])

        assert dao.delete_for_user("u-1", "d") is True
        eq1.assert_called_with("id", "d")
        eq1.return_value.eq.assert_called_with("user_id", "u-1")

    def test_delete_for_user_returns_false_when_nothing_matched(self):
        dao, client = _make()
        eq1 = client.table.return_value.delete.return_value.eq
        eq1.return_value.eq.return_value.execute.return_value = _result([])
        assert dao.delete_for_user("u-other", "d") is False

    def test_delete_by_fid(self):
        dao, client = _make()
        eq = client.table.return_value.delete.return_value.eq
        eq.return_value.execute.return_value = _result([{"id": "d"}])
        assert dao.delete_by_fid(FID) is True
        eq.assert_called_with("fid", FID)

    def test_delete_errors_return_false(self):
        dao, client = _make()
        client.table.side_effect = RuntimeError("down")
        assert dao.delete_for_user("u-1", "d") is False
        assert dao.delete_by_fid(FID) is False
