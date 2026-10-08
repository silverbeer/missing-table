"""APNs device endpoints + iOS leg of the test notification (SB-1236).

Minimal FastAPI app with the push router; auth is overridden to a stub user
and the DAOs are replaced with mocks, so nothing touches the DB or APNs.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notifications.web_push_sender import SendResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

TOKEN = "AB" * 32  # valid hex, upper-case on purpose
USER = {"id": "u-1", "role": "user", "username": "tom"}


@pytest.fixture
def api(monkeypatch):
    from api import push
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(push.router)
    app.dependency_overrides[get_current_user_required] = lambda: USER

    apns_dao = MagicMock()
    log_dao = MagicMock()
    sub_dao = MagicMock()
    monkeypatch.setattr(push, "_apns_dao", lambda: apns_dao)
    monkeypatch.setattr(push, "_log_dao", lambda: log_dao)
    monkeypatch.setattr(push, "_sub_dao", lambda: sub_dao)
    monkeypatch.setattr(push, "_check_test_rate_limit", lambda _uid: None)
    return TestClient(app), push, apns_dao, log_dao, sub_dao


class TestRegister:
    def _row(self):
        return {
            "id": "dev-1",
            "user_id": "u-1",
            "device_token": TOKEN.lower(),
            "environment": "production",
            "bundle_id": "com.missingtable",
            "device_label": "Tom's iPhone",
            "app_version": "1.0 (3)",
            "created_at": "2026-10-04T00:00:00Z",
            "last_seen_at": "2026-10-04T00:00:00Z",
        }

    def test_registers_and_returns_201_without_token(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.upsert.return_value = self._row()

        resp = client.post(
            "/api/users/me/apns-devices",
            json={
                "device_token": TOKEN,
                "environment": "production",
                "device_label": "Tom's iPhone",
                "app_version": "1.0 (3)",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "dev-1"
        assert body["environment"] == "production"
        assert "device_token" not in body
        apns_dao.upsert.assert_called_once_with(
            user_id="u-1",
            device_token=TOKEN.lower(),
            environment="production",
            device_label="Tom's iPhone",
            app_version="1.0 (3)",
        )

    def test_optional_fields_may_be_omitted(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.upsert.return_value = self._row()
        resp = client.post("/api/users/me/apns-devices", json={"device_token": TOKEN, "environment": "sandbox"})
        assert resp.status_code == 201

    @pytest.mark.parametrize(
        "token",
        [
            "ab" * 31,  # 62 chars — too short
            "a" * 201,  # too long
            "zz" * 32,  # not hex
            "<" + "a" * 63,
            "",
        ],
    )
    def test_rejects_malformed_tokens(self, api, token):
        client, _, apns_dao, _, _ = api
        resp = client.post("/api/users/me/apns-devices", json={"device_token": token, "environment": "sandbox"})
        assert resp.status_code == 422
        apns_dao.upsert.assert_not_called()

    def test_accepts_longer_tokens_up_to_200(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.upsert.return_value = self._row()
        resp = client.post("/api/users/me/apns-devices", json={"device_token": "a" * 200, "environment": "sandbox"})
        assert resp.status_code == 201

    def test_rejects_unknown_environment(self, api):
        client, _, apns_dao, _, _ = api
        resp = client.post("/api/users/me/apns-devices", json={"device_token": TOKEN, "environment": "development"})
        assert resp.status_code == 422
        apns_dao.upsert.assert_not_called()

    def test_rejects_overlong_label(self, api):
        client, _, _, _, _ = api
        resp = client.post(
            "/api/users/me/apns-devices",
            json={"device_token": TOKEN, "environment": "sandbox", "device_label": "x" * 101},
        )
        assert resp.status_code == 422

    def test_dao_failure_is_500(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.upsert.return_value = None
        resp = client.post("/api/users/me/apns-devices", json={"device_token": TOKEN, "environment": "sandbox"})
        assert resp.status_code == 500


class TestListAndDelete:
    def test_lists_own_devices(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.list_by_user.return_value = [{"id": "dev-1", "environment": "sandbox"}]
        resp = client.get("/api/users/me/apns-devices")
        assert resp.status_code == 200
        assert resp.json() == {"devices": [{"id": "dev-1", "environment": "sandbox"}]}
        apns_dao.list_by_user.assert_called_once_with("u-1")

    def test_delete_own_device_is_204(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.delete_for_user.return_value = True
        resp = client.delete("/api/users/me/apns-devices/dev-1")
        assert resp.status_code == 204
        apns_dao.delete_for_user.assert_called_once_with("u-1", "dev-1")

    def test_delete_unknown_or_foreign_device_is_404(self, api):
        client, _, apns_dao, _, _ = api
        apns_dao.delete_for_user.return_value = False
        resp = client.delete("/api/users/me/apns-devices/someone-elses")
        assert resp.status_code == 404


class TestAuthRequired:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("post", "/api/users/me/apns-devices"),
            ("get", "/api/users/me/apns-devices"),
            ("delete", "/api/users/me/apns-devices/dev-1"),
        ],
    )
    def test_unauthenticated_is_rejected(self, method, path):
        from api import push

        app = FastAPI()
        app.include_router(push.router)
        client = TestClient(app)
        kwargs = {"json": {"device_token": TOKEN, "environment": "sandbox"}} if method == "post" else {}
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code in (401, 403)


class TestTestNotification:
    def _configure(self, monkeypatch, push, web, apns):
        monkeypatch.setattr(push, "push_is_configured", lambda: web)
        monkeypatch.setattr(push, "apns_is_configured", lambda: apns)

    def test_sends_to_ios_devices(self, api, monkeypatch):
        client, push, apns_dao, log_dao, _ = api
        self._configure(monkeypatch, push, web=False, apns=True)
        apns_dao.list_for_user_ids.return_value = [
            {"id": "dev-1", "user_id": "u-1", "device_token": "aa" * 32, "environment": "sandbox"},
        ]
        send = MagicMock(return_value=SendResult(status="sent", http_status=200))
        monkeypatch.setattr(push, "send_apns", send)

        resp = client.post("/api/users/me/notifications/test")

        assert resp.status_code == 200
        assert resp.json() == {"sent": 1, "failed": 0, "expired": 0, "subscriptions": 0, "apns_devices": 1}
        apns_dao.list_for_user_ids.assert_called_once_with(["u-1"])
        assert send.call_args.args[1]["tag"] == "mt-test"
        log = log_dao.log.call_args.kwargs
        assert log["platform"] == "apns"
        assert log["apns_device_id"] == "dev-1"
        assert log["subscription_id"] is None
        assert log["event_type"] == "test"

    def test_expired_ios_device_is_deleted(self, api, monkeypatch):
        client, push, apns_dao, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=True)
        apns_dao.list_for_user_ids.return_value = [
            {"id": "dev-1", "user_id": "u-1", "device_token": "aa" * 32, "environment": "sandbox"},
        ]
        monkeypatch.setattr(push, "send_apns", lambda *_: SendResult(status="expired", http_status=410))

        resp = client.post("/api/users/me/notifications/test")

        assert resp.json()["expired"] == 1
        apns_dao.delete_by_token.assert_called_once_with("aa" * 32)

    def test_web_and_ios_together(self, api, monkeypatch):
        client, push, apns_dao, _, sub_dao = api
        self._configure(monkeypatch, push, web=True, apns=True)
        sub_dao.list_by_user.return_value = [{"id": "sub-1"}]
        conn = MagicMock()
        conn.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "sub-1", "endpoint": "https://push/x", "p256dh_key": "k", "auth_key": "a"}
        ]
        monkeypatch.setattr(push, "_conn", lambda: conn)
        apns_dao.list_for_user_ids.return_value = [
            {"id": "dev-1", "user_id": "u-1", "device_token": "aa" * 32, "environment": "sandbox"},
        ]
        monkeypatch.setattr(push, "send_push", lambda *_: SendResult(status="sent", http_status=201))
        monkeypatch.setattr(push, "send_apns", lambda *_: SendResult(status="failed", http_status=500))

        resp = client.post("/api/users/me/notifications/test")

        assert resp.json() == {"sent": 1, "failed": 1, "expired": 0, "subscriptions": 1, "apns_devices": 1}

    def test_apns_unconfigured_skips_device_lookup(self, api, monkeypatch):
        client, push, apns_dao, _, sub_dao = api
        self._configure(monkeypatch, push, web=True, apns=False)
        sub_dao.list_by_user.return_value = []
        conn = MagicMock()
        conn.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        monkeypatch.setattr(push, "_conn", lambda: conn)

        resp = client.post("/api/users/me/notifications/test")

        assert resp.status_code == 200
        assert resp.json()["sent"] == 0
        apns_dao.list_for_user_ids.assert_not_called()

    def test_neither_configured_is_503(self, api, monkeypatch):
        client, push, _, _, _ = api
        self._configure(monkeypatch, push, web=False, apns=False)
        resp = client.post("/api/users/me/notifications/test")
        assert resp.status_code == 503
