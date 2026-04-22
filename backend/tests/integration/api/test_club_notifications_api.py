"""
API contract / integration tests for club notification channel endpoints.

Uses FastAPI TestClient with `app.dependency_overrides` to impersonate each
role, and the real local Supabase for DAO-layer state. Covers permissions,
masking, validation, the NOTIFICATIONS_ENABLED kill switch, and the
Redis-backed rate limiter on test-send.

The tests mock `_send_test_message` so they don't require Phase 5 sending
code. They also patch `check_rate_limit` where determinism matters, since
the real limiter uses wall-clock minute buckets.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import club_notifications as api_module
from app import app
from auth import get_current_user_required
from dao.club_dao import ClubDAO
from dao.club_notifications_dao import ClubNotificationsDAO
from dao.match_dao import SupabaseConnection

pytestmark = [pytest.mark.integration, pytest.mark.api]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_name() -> str:
    return f"NotifyApi-{uuid.uuid4().hex[:8]}"


def _fake_user(role: str, club_id: int | None = None, user_id: str = "u-1"):
    return {
        "user_id": user_id,
        "username": f"{role}_user",
        "role": role,
        "email": f"{role}@example.com",
        "team_id": None,
        "club_id": club_id,
        "display_name": f"{role.title()} User",
    }


@contextmanager
def as_user(user: dict):
    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    return SupabaseConnection()


@pytest.fixture
def club_dao(conn):
    return ClubDAO(conn)


@pytest.fixture
def notif_dao(conn):
    return ClubNotificationsDAO(conn)


@pytest.fixture
def club(club_dao):
    c = club_dao.create_club(name=_unique_name(), city="Boston")
    yield c
    try:
        club_dao.delete_club(c["id"])
    except Exception:
        pass


@pytest.fixture
def other_club(club_dao):
    c = club_dao.create_club(name=_unique_name(), city="NYC")
    yield c
    try:
        club_dao.delete_club(c["id"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GET /api/clubs/{club_id}/notifications
# ---------------------------------------------------------------------------


class TestListChannels:
    def test_empty_list_for_unconfigured_club(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.get(f"/api/clubs/{club['id']}/notifications")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_configured_channels_with_masked_destination(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-1001234567890")
        with as_user(_fake_user("admin")) as c:
            r = c.get(f"/api/clubs/{club['id']}/notifications")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["platform"] == "telegram"
        assert data[0]["configured"] is True
        assert data[0]["enabled"] is True
        assert data[0]["hint"] == "7890"  # last 4 of destination
        assert "destination" not in data[0]  # full value never exposed

    def test_club_manager_sees_own_club(self, club, notif_dao):
        notif_dao.upsert(club["id"], "discord", "https://discord.com/api/webhooks/9/xyz9")
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.get(f"/api/clubs/{club['id']}/notifications")
        assert r.status_code == 200
        assert r.json()[0]["hint"] == "xyz9"

    def test_club_manager_denied_other_club(self, club, other_club, notif_dao):
        notif_dao.upsert(other_club["id"], "telegram", "-100aaa")
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.get(f"/api/clubs/{other_club['id']}/notifications")
        assert r.status_code == 403

    def test_regular_user_denied(self, club):
        with as_user(_fake_user("user")) as c:
            r = c.get(f"/api/clubs/{club['id']}/notifications")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/clubs/{club_id}/notifications/{platform}
# ---------------------------------------------------------------------------


class TestUpsertChannel:
    def test_admin_creates_telegram(self, club, notif_dao):
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/telegram",
                json={"destination": "-1001112223334", "enabled": True},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["platform"] == "telegram"
        assert body["enabled"] is True
        assert body["hint"] == "3334"
        # DB side: destination stored in full
        stored = notif_dao.get(club["id"], "telegram")
        assert stored["destination"] == "-1001112223334"

    def test_admin_creates_discord_webhook(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/discord",
                json={
                    "destination": "https://discord.com/api/webhooks/12345/abc-DEF_token123",
                    "enabled": True,
                },
            )
        assert r.status_code == 200
        assert r.json()["hint"] == "n123"

    def test_admin_overwrites_existing_channel(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-1000000000001")
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/telegram",
                json={"destination": "-1000000000002", "enabled": False},
            )
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert notif_dao.get(club["id"], "telegram")["destination"] == "-1000000000002"

    def test_club_manager_creates_for_own_club(self, club):
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/telegram",
                json={"destination": "-1009999", "enabled": True},
            )
        assert r.status_code == 200

    def test_club_manager_denied_other_club(self, other_club, club):
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.put(
                f"/api/clubs/{other_club['id']}/notifications/telegram",
                json={"destination": "-100abc", "enabled": True},
            )
        assert r.status_code == 403

    def test_regular_user_denied(self, club):
        with as_user(_fake_user("user")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/telegram",
                json={"destination": "-100abc", "enabled": True},
            )
        assert r.status_code == 403

    def test_invalid_telegram_destination_rejected(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/telegram",
                json={"destination": "not-a-chat-id", "enabled": True},
            )
        assert r.status_code == 422

    def test_invalid_discord_destination_rejected(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/discord",
                json={"destination": "https://example.com/hook", "enabled": True},
            )
        assert r.status_code == 422

    def test_unknown_platform_rejected(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.put(
                f"/api/clubs/{club['id']}/notifications/sms",
                json={"destination": "555-1212", "enabled": True},
            )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/clubs/{club_id}/notifications/{platform}
# ---------------------------------------------------------------------------


class TestDeleteChannel:
    def test_admin_deletes(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-100xxxx")
        with as_user(_fake_user("admin")) as c:
            r = c.delete(f"/api/clubs/{club['id']}/notifications/telegram")
        assert r.status_code == 204
        assert notif_dao.get(club["id"], "telegram") is None

    def test_delete_nonexistent_still_204(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.delete(f"/api/clubs/{club['id']}/notifications/telegram")
        assert r.status_code == 204

    def test_club_manager_denied_other_club(self, club, other_club):
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.delete(f"/api/clubs/{other_club['id']}/notifications/telegram")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/clubs/{club_id}/notifications/{platform}/test
# ---------------------------------------------------------------------------


class TestTestSend:
    def test_returns_501_when_sender_not_implemented(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-100sendtest1")
        with as_user(_fake_user("admin")) as c:
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 501  # Phase 3 stub raises NotImplementedError

    def test_success_when_sender_mocked(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-100sendtest2")
        with (
            patch.object(api_module, "_send_test_message", return_value=None),
            as_user(_fake_user("admin")) as c,
        ):
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 200
        assert r.json() == {"success": True, "error": None}

    def test_404_when_no_channel_configured(self, club):
        with as_user(_fake_user("admin")) as c:
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 404

    def test_503_when_notifications_disabled(self, club, notif_dao, monkeypatch):
        notif_dao.upsert(club["id"], "telegram", "-100off")
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", "false")
        with as_user(_fake_user("admin")) as c:
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 503

    def test_429_when_rate_limit_exceeded(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-100ratelimited")
        with (
            patch.object(api_module, "check_rate_limit", return_value=False),
            patch.object(api_module, "_send_test_message", return_value=None),
            as_user(_fake_user("admin")) as c,
        ):
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 429

    def test_reports_sender_exception_without_leaking_destination(
        self, club, notif_dao, caplog
    ):
        notif_dao.upsert(club["id"], "telegram", "-100shouldNotAppearInLogs")

        def _boom(platform, destination):
            raise RuntimeError("upstream down")

        with (
            patch.object(api_module, "_send_test_message", side_effect=_boom),
            as_user(_fake_user("admin")) as c,
        ):
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")

        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert body["error"] == "RuntimeError"
        # Destination value must not leak into logs
        assert "shouldNotAppearInLogs" not in caplog.text

    def test_club_manager_can_test_own_club(self, club, notif_dao):
        notif_dao.upsert(club["id"], "telegram", "-100mgr")
        with (
            patch.object(api_module, "_send_test_message", return_value=None),
            as_user(_fake_user("club_manager", club_id=club["id"])) as c,
        ):
            r = c.post(f"/api/clubs/{club['id']}/notifications/telegram/test")
        assert r.status_code == 200

    def test_club_manager_denied_other_club(self, other_club, club, notif_dao):
        notif_dao.upsert(other_club["id"], "telegram", "-100xxx")
        with as_user(_fake_user("club_manager", club_id=club["id"])) as c:
            r = c.post(f"/api/clubs/{other_club['id']}/notifications/telegram/test")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Rate limiter unit tests
# ---------------------------------------------------------------------------


class TestRateLimiterHelper:
    def test_fail_open_when_redis_unreachable(self, monkeypatch):
        """If Redis isn't there, we never block requests."""
        monkeypatch.setattr(api_module, "_redis_client", None)
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1")  # wrong port
        # Reset the module-level client so _get_redis() retries
        api_module._redis_client = None
        assert api_module.check_rate_limit("t", max_per_minute=1) is True

    def test_counts_requests_within_a_minute(self):
        """Real Redis exercise: six calls, first 5 allowed, 6th blocked."""
        # Skip gracefully if Redis isn't available locally.
        if api_module._get_redis() is None:
            pytest.skip("Redis not available")

        key = f"ratelimit-test-{uuid.uuid4().hex[:8]}"
        results = [api_module.check_rate_limit(key, max_per_minute=5) for _ in range(6)]
        assert results[:5] == [True] * 5
        assert results[5] is False


# ---------------------------------------------------------------------------
# Kill switch helper
# ---------------------------------------------------------------------------


class TestKillSwitch:
    def test_default_true(self, monkeypatch):
        monkeypatch.delenv("NOTIFICATIONS_ENABLED", raising=False)
        assert api_module.is_notifications_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE", "Off"])
    def test_falsy_values_disable(self, monkeypatch, val):
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", val)
        assert api_module.is_notifications_enabled() is False

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "TRUE"])
    def test_truthy_values_enable(self, monkeypatch, val):
        monkeypatch.setenv("NOTIFICATIONS_ENABLED", val)
        assert api_module.is_notifications_enabled() is True
