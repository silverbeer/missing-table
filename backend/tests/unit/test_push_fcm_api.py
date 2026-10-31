"""FCM device endpoints + Android leg of the test notification (SB-1463).

Minimal FastAPI app with the push router; auth is overridden to a stub user
and the DAOs are replaced with mocks, so nothing touches the DB or FCM.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

FID = "cJx1Yk2zQ9-abc_DEF0123"
USER = {"id": "u-1", "role": "user", "username": "tom"}


@pytest.fixture
def api(monkeypatch):
    from api import push
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(push.router)
    app.dependency_overrides[get_current_user_required] = lambda: USER

    fcm_dao = MagicMock()
    apns_dao = MagicMock()
    log_dao = MagicMock()
    sub_dao = MagicMock()
    monkeypatch.setattr(push, "_fcm_dao", lambda: fcm_dao)
    monkeypatch.setattr(push, "_apns_dao", lambda: apns_dao)
    monkeypatch.setattr(push, "_log_dao", lambda: log_dao)
    monkeypatch.setattr(push, "_sub_dao", lambda: sub_dao)
    monkeypatch.setattr(push, "_check_test_rate_limit", lambda _uid: None)
    return TestClient(app), push, fcm_dao, apns_dao, log_dao, sub_dao


class TestRegister:
    def _row(self):
        return {
            "id": "dev-1",
            "user_id": "u-1",
            "fid": FID,
            "device_label": "Pixel 9",
            "app_version": "0.2.18",
            "created_at": "2026-10-31T00:00:00Z",
            "last_seen_at": "2026-10-31T00:00:00Z",
        }

    def test_registers_and_returns_201_without_fid(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.upsert.return_value = self._row()

        resp = client.post(
            "/api/users/me/fcm-devices",
            json={"fid": FID, "app_version": "0.2.18", "device_label": "Pixel 9"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "dev-1"
        assert body["app_version"] == "0.2.18"
        assert "fid" not in body
        fcm_dao.upsert.assert_called_once_with(
            user_id="u-1",
            fid=FID,
            device_label="Pixel 9",
            app_version="0.2.18",
        )

    def test_optional_fields_may_be_omitted(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.upsert.return_value = self._row()
        resp = client.post("/api/users/me/fcm-devices", json={"fid": FID})
        assert resp.status_code == 201

    @pytest.mark.parametrize(
        "fid",
        [
            "",
            "   ",
            "x" * 256,  # over the cap — would otherwise 500 on the btree index
            "has space",
            "<script>",
            "a/b",
            "émoji",
        ],
    )
    def test_rejects_malformed_fids(self, api, fid):
        client, _, fcm_dao, _, _, _ = api
        resp = client.post("/api/users/me/fcm-devices", json={"fid": fid})
        assert resp.status_code == 422
        fcm_dao.upsert.assert_not_called()

    def test_accepts_255_chars_and_strips_whitespace(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.upsert.return_value = self._row()
        assert client.post("/api/users/me/fcm-devices", json={"fid": "a" * 255}).status_code == 201
        resp = client.post("/api/users/me/fcm-devices", json={"fid": f"  {FID}\n"})
        assert resp.status_code == 201
        assert fcm_dao.upsert.call_args.kwargs["fid"] == FID

    def test_legacy_token_field_is_not_accepted(self, api):
        client, _, fcm_dao, _, _, _ = api
        resp = client.post("/api/users/me/fcm-devices", json={"token": "fcm-token:APA91b"})
        assert resp.status_code == 422
        fcm_dao.upsert.assert_not_called()

    def test_rejects_missing_fid(self, api):
        client, _, fcm_dao, _, _, _ = api
        resp = client.post("/api/users/me/fcm-devices", json={"app_version": "0.2.18"})
        assert resp.status_code == 422
        fcm_dao.upsert.assert_not_called()

    def test_rejects_overlong_label(self, api):
        client, _, _, _, _, _ = api
        resp = client.post("/api/users/me/fcm-devices", json={"fid": FID, "device_label": "x" * 101})
        assert resp.status_code == 422

    def test_dao_failure_is_500(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.upsert.return_value = None
        resp = client.post("/api/users/me/fcm-devices", json={"fid": FID})
        assert resp.status_code == 500


class TestListAndDelete:
    def test_lists_own_devices(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.list_by_user.return_value = [{"id": "dev-1", "app_version": "0.2.18"}]
        resp = client.get("/api/users/me/fcm-devices")
        assert resp.status_code == 200
        assert resp.json() == {"devices": [{"id": "dev-1", "app_version": "0.2.18"}]}
        fcm_dao.list_by_user.assert_called_once_with("u-1")

    def test_delete_own_device_is_204(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.delete_for_user.return_value = True
        resp = client.delete("/api/users/me/fcm-devices/dev-1")
        assert resp.status_code == 204
        fcm_dao.delete_for_user.assert_called_once_with("u-1", "dev-1")

    def test_delete_unknown_or_foreign_device_is_404(self, api):
        client, _, fcm_dao, _, _, _ = api
        fcm_dao.delete_for_user.return_value = False
        resp = client.delete("/api/users/me/fcm-devices/someone-elses")
        assert resp.status_code == 404


class TestAuthRequired:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("post", "/api/users/me/fcm-devices"),
            ("get", "/api/users/me/fcm-devices"),
            ("delete", "/api/users/me/fcm-devices/dev-1"),
        ],
    )
    def test_unauthenticated_is_rejected(self, method, path):
        from api import push

        app = FastAPI()
        app.include_router(push.router)
        client = TestClient(app)
        kwargs = {"json": {"fid": FID}} if method == "post" else {}
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code in (401, 403)


class TestTestNotification:
    def _configure(self, monkeypatch, push, web, apns, fcm):
        monkeypatch.setattr(push, "push_is_configured", lambda: web)
        monkeypatch.setattr(push, "apns_is_configured", lambda: apns)
        monkeypatch.setattr(push, "fcm_is_configured", lambda: fcm)

    def test_sends_to_android_devices_when_fcm_is_the_only_channel(self, api, monkeypatch):
        client, push, fcm_dao, apns_dao, log_dao, _ = api
        self._configure(monkeypatch, push, web=False, apns=False, fcm=True)
        fcm_dao.list_for_user_ids.return_value = [{"id": "dev-1", "user_id": "u-1", "fid": FID}]
        send = MagicMock(return_value=SendResult(status="sent", http_status=200))
        monkeypatch.setattr(push, "send_fcm", send)

        resp = client.post("/api/users/me/notifications/test")

        assert resp.status_code == 200
        assert resp.json() == {
            "sent": 1,
            "failed": 0,
            "expired": 0,
            "subscriptions": 0,
            "apns_devices": 0,
            "fcm_devices": 1,
        }
        fcm_dao.list_for_user_ids.assert_called_once_with(["u-1"])
        apns_dao.list_for_user_ids.assert_not_called()
        assert send.call_args.args[0]["fid"] == FID
        assert send.call_args.args[1]["tag"] == "mt-test"
        log = log_dao.log.call_args.kwargs
        assert log["platform"] == "fcm"
        assert log["fcm_device_id"] == "dev-1"
        assert log["subscription_id"] is None
        assert log["event_type"] == "test"

    def test_expired_android_device_is_deleted(self, api, monkeypatch):
        client, push, fcm_dao, _, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=False, fcm=True)
        fcm_dao.list_for_user_ids.return_value = [{"id": "dev-1", "user_id": "u-1", "fid": FID}]
        monkeypatch.setattr(push, "send_fcm", lambda *_: SendResult(status="expired", http_status=404))

        resp = client.post("/api/users/me/notifications/test")

        assert resp.json()["expired"] == 1
        fcm_dao.delete_by_fid.assert_called_once_with(FID)

    def test_ios_and_android_together(self, api, monkeypatch):
        client, push, fcm_dao, apns_dao, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=True, fcm=True)
        apns_dao.list_for_user_ids.return_value = [
            {"id": "a-1", "user_id": "u-1", "device_token": "aa" * 32, "environment": "sandbox"},
        ]
        fcm_dao.list_for_user_ids.return_value = [{"id": "f-1", "user_id": "u-1", "fid": FID}]
        monkeypatch.setattr(push, "send_apns", lambda *_: SendResult(status="sent", http_status=200))
        monkeypatch.setattr(push, "send_fcm", lambda *_: SendResult(status="failed", http_status=503))

        resp = client.post("/api/users/me/notifications/test")

        assert resp.json() == {
            "sent": 1,
            "failed": 1,
            "expired": 0,
            "subscriptions": 0,
            "apns_devices": 1,
            "fcm_devices": 1,
        }
        fcm_dao.delete_by_fid.assert_not_called()

    def test_fcm_unconfigured_skips_device_lookup(self, api, monkeypatch):
        client, push, fcm_dao, apns_dao, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=True, fcm=False)
        apns_dao.list_for_user_ids.return_value = []
        send = MagicMock()
        monkeypatch.setattr(push, "send_fcm", send)

        resp = client.post("/api/users/me/notifications/test")

        assert resp.status_code == 200
        assert resp.json()["fcm_devices"] == 0
        fcm_dao.list_for_user_ids.assert_not_called()
        send.assert_not_called()

    def test_no_devices_anywhere_returns_full_summary(self, api, monkeypatch):
        client, push, fcm_dao, _, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=False, fcm=True)
        fcm_dao.list_for_user_ids.return_value = []
        resp = client.post("/api/users/me/notifications/test")
        assert resp.json() == {
            "sent": 0,
            "failed": 0,
            "expired": 0,
            "subscriptions": 0,
            "apns_devices": 0,
            "fcm_devices": 0,
        }

    def test_none_configured_is_503(self, api, monkeypatch):
        client, push, _, _, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=False, fcm=False)
        resp = client.post("/api/users/me/notifications/test")
        assert resp.status_code == 503
