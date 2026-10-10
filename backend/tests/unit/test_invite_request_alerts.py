"""Admin ping on new invite requests (SB-1313).

Only a genuinely new row pings: honeypot hits and duplicate pending
submissions are silent, and a broken or unconfigured sender never costs the
requester their 201.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from notifications.invite_request_alerts import (
    DISCORD_WEBHOOK_ENV,
    TELEGRAM_CHAT_ID_ENV,
    format_invite_request_alert,
    notify_new_invite_request,
)

PAYLOAD = {"email": "fan@example.com", "name": "Pat Fan", "team": "IFA U14", "reason": "Saw the post"}


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "-100123")
    monkeypatch.setenv(DISCORD_WEBHOOK_ENV, "https://discord.com/api/webhooks/1/abc")
    monkeypatch.setenv("APP_BASE_URL", "https://mt.example")


@pytest.fixture
def no_admin_env(monkeypatch):
    monkeypatch.delenv(TELEGRAM_CHAT_ID_ENV, raising=False)
    monkeypatch.delenv(DISCORD_WEBHOOK_ENV, raising=False)


def _db(existing=None, inserted=None):
    """A service_client whose select returns `existing` and insert returns `inserted`."""
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=existing or []
    )
    table.insert.return_value.execute.return_value = SimpleNamespace(
        data=inserted if inserted is not None else [{"id": "r1"}]
    )
    return client


@pytest.fixture
def api():
    from api import invite_requests

    app = FastAPI()
    app.include_router(invite_requests.router)
    return invite_requests, TestClient(app)


@pytest.mark.unit
class TestEndpointPings:
    def test_new_request_pings(self, api, admin_env):
        module, client = api
        with (
            patch.object(module, "service_client", _db()),
            patch("notifications.invite_request_alerts.send_to") as send,
        ):
            resp = client.post("/api/invite-requests", json=PAYLOAD)
        assert resp.status_code == 201
        assert [c.args[0] for c in send.call_args_list] == ["telegram", "discord"]
        content = send.call_args_list[0].args[2]
        assert "Pat Fan" in content
        assert "IFA U14" in content
        assert "https://mt.example/" in content
        assert "fan@example.com" not in content

    def test_honeypot_does_not_ping(self, api, admin_env):
        module, client = api
        db = _db()
        with (
            patch.object(module, "service_client", db),
            patch("notifications.invite_request_alerts.send_to") as send,
        ):
            resp = client.post("/api/invite-requests", json={**PAYLOAD, "website": "http://spam"})
        assert resp.status_code == 201
        send.assert_not_called()
        db.table.return_value.insert.assert_not_called()

    def test_duplicate_pending_does_not_ping(self, api, admin_env):
        module, client = api
        db = _db(existing=[{"id": "r0", "status": "pending"}])
        with (
            patch.object(module, "service_client", db),
            patch("notifications.invite_request_alerts.send_to") as send,
        ):
            resp = client.post("/api/invite-requests", json=PAYLOAD)
        assert resp.status_code == 201
        send.assert_not_called()
        db.table.return_value.insert.assert_not_called()

    def test_unconfigured_is_a_noop(self, api, no_admin_env):
        module, client = api
        with (
            patch.object(module, "service_client", _db()),
            patch("notifications.invite_request_alerts.send_to") as send,
        ):
            resp = client.post("/api/invite-requests", json=PAYLOAD)
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        send.assert_not_called()

    def test_request_succeeds_when_sender_raises(self, api, admin_env):
        module, client = api
        with (
            patch.object(module, "service_client", _db()),
            patch("notifications.invite_request_alerts.send_to", side_effect=RuntimeError("boom")) as send,
        ):
            resp = client.post("/api/invite-requests", json=PAYLOAD)
        assert resp.status_code == 201
        assert resp.json()["success"] is True
        # Discord is still tried after Telegram fails.
        assert send.call_count == 2


@pytest.mark.unit
class TestNotifier:
    def test_one_destination_is_enough(self, monkeypatch, no_admin_env):
        monkeypatch.setenv(TELEGRAM_CHAT_ID_ENV, "-100123")
        with patch("notifications.invite_request_alerts.send_to") as send:
            assert notify_new_invite_request("Pat", None) == 1
        send.assert_called_once()
        assert send.call_args.args[:2] == ("telegram", "-100123")

    def test_never_raises(self, admin_env):
        with patch("notifications.invite_request_alerts.send_to", side_effect=Exception("down")):
            assert notify_new_invite_request("Pat", "Team") == 0


@pytest.mark.unit
class TestFormat:
    def test_ios_beta_line_only_when_true(self, admin_env):
        assert "iPhone beta: yes" in format_invite_request_alert("Pat", "T", True)
        assert "iPhone beta" not in format_invite_request_alert("Pat", "T", False)

    def test_missing_team(self, admin_env):
        assert "Team: —" in format_invite_request_alert("Pat", None, False)

    def test_mentions_are_defanged(self, admin_env):
        content = format_invite_request_alert("@everyone", "@here", False)
        assert "@everyone" not in content
        assert "@here" not in content
