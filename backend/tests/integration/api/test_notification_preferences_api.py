"""API contract tests for the per-event notification preferences endpoints (SB-57).

The DAO is patched so these are pure FastAPI contract tests — verifying
auth, validation, and response shape without round-tripping through the DB.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from notifications.preferences import DEFAULT_PREFERENCES, EVENT_TYPES

pytestmark = [pytest.mark.unit, pytest.mark.api]


def _fake_user(user_id: str = "u-prefs-1") -> dict:
    return {
        "user_id": user_id,
        "username": "prefs_tester",
        "role": "club_fan",
        "email": "prefs@example.com",
        "team_id": None,
        "club_id": None,
        "display_name": "Prefs Tester",
    }


@contextmanager
def _as_user(user: dict):
    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


@contextmanager
def _patched_prefs_dao(dao_mock: MagicMock):
    with patch("api.push._prefs_dao", return_value=dao_mock):
        yield


class TestGetPreferences:
    def test_returns_full_dict_with_defaults_applied(self):
        dao = MagicMock()
        dao.get_preferences.return_value = dict(DEFAULT_PREFERENCES)

        with _as_user(_fake_user()), _patched_prefs_dao(dao):
            with TestClient(app) as client:
                resp = client.get("/api/users/me/notification-preferences")

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["preferences"].keys()) == set(EVENT_TYPES)
        assert body["preferences"]["yellow_card"] is False
        assert body["preferences"]["goal"] is True

    def test_passes_user_id_to_dao(self):
        dao = MagicMock()
        dao.get_preferences.return_value = dict(DEFAULT_PREFERENCES)

        with _as_user(_fake_user(user_id="abc-123")), _patched_prefs_dao(dao):
            with TestClient(app) as client:
                client.get("/api/users/me/notification-preferences")

        dao.get_preferences.assert_called_once_with("abc-123")

    def test_unauthenticated_returns_401(self):
        # No dependency override → real auth dependency runs → 401.
        with TestClient(app) as client:
            resp = client.get("/api/users/me/notification-preferences")
        assert resp.status_code in (401, 403)


class TestPutPreferences:
    def test_updates_and_returns_merged_state(self):
        dao = MagicMock()
        # After upsert, the DAO returns the new merged state.
        merged = {**DEFAULT_PREFERENCES, "goal": False, "yellow_card": True}
        dao.set_preferences.return_value = merged

        with _as_user(_fake_user()), _patched_prefs_dao(dao):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/users/me/notification-preferences",
                    json={"preferences": {"goal": False, "yellow_card": True}},
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["preferences"]["goal"] is False
        assert body["preferences"]["yellow_card"] is True

        dao.set_preferences.assert_called_once()
        call_args = dao.set_preferences.call_args
        # First arg: user_id; second: prefs dict.
        assert call_args.args[1] == {"goal": False, "yellow_card": True}

    def test_unknown_event_type_returns_422(self):
        dao = MagicMock()

        with _as_user(_fake_user()), _patched_prefs_dao(dao):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/users/me/notification-preferences",
                    json={"preferences": {"goal": True, "bogus_event": False}},
                )

        assert resp.status_code == 422
        assert "bogus_event" in resp.text
        dao.set_preferences.assert_not_called()

    def test_empty_preferences_is_a_no_op_but_returns_current_state(self):
        dao = MagicMock()
        dao.set_preferences.return_value = dict(DEFAULT_PREFERENCES)

        with _as_user(_fake_user()), _patched_prefs_dao(dao):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/users/me/notification-preferences",
                    json={"preferences": {}},
                )

        assert resp.status_code == 200
        assert resp.json()["preferences"] == DEFAULT_PREFERENCES
        # Still called the DAO; DAO is responsible for the "no rows → fall through" behavior.
        dao.set_preferences.assert_called_once()

    def test_missing_preferences_field_returns_422(self):
        with _as_user(_fake_user()):
            with TestClient(app) as client:
                resp = client.put(
                    "/api/users/me/notification-preferences",
                    json={},
                )
        assert resp.status_code == 422
