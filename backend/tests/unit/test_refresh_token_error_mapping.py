"""Unit tests for /api/auth/refresh error mapping (SB-123).

The endpoint previously mapped *every* failure to HTTP 401. The frontend
treats 401/403 from a refresh as a genuine auth failure and force-logs-out,
so a transient upstream hiccup (network not ready on wake-from-sleep, a slow
or 5xx Supabase response) became a needless re-login — the "logged out after
idle" bug.

Correct mapping:
- genuine bad/expired/used token (AuthApiError) -> 401 (frontend logs out)
- transient (AuthRetryableError, network, anything else) -> 503 (frontend
  keeps the token and recovers on the next refresh)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from gotrue.errors import AuthApiError, AuthRetryableError

import app as app_module

REFRESH_URL = "/api/auth/refresh"
BODY = {"refresh_token": "some-refresh-token"}


@pytest.fixture
def client():
    return TestClient(app_module.app)


def _session_response():
    return SimpleNamespace(
        session=SimpleNamespace(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_at=1234567890,
        )
    )


class TestRefreshErrorMapping:
    def test_success_returns_new_session(self, client):
        with patch.object(app_module.auth_ops_client.auth, "refresh_session", return_value=_session_response()):
            resp = client.post(REFRESH_URL, json=BODY)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["session"]["access_token"] == "new-access"
        assert body["session"]["refresh_token"] == "new-refresh"

    def test_genuine_bad_token_returns_401(self, client):
        err = AuthApiError("invalid refresh token", 400, "refresh_token_not_found")
        with patch.object(app_module.auth_ops_client.auth, "refresh_session", side_effect=err):
            resp = client.post(REFRESH_URL, json=BODY)
        assert resp.status_code == 401

    def test_retryable_error_returns_503(self, client):
        # AuthRetryableError = upstream said "retry" (e.g. 5xx). Transient.
        err = AuthRetryableError("service unavailable", 503)
        with patch.object(app_module.auth_ops_client.auth, "refresh_session", side_effect=err):
            resp = client.post(REFRESH_URL, json=BODY)
        assert resp.status_code == 503

    def test_network_error_returns_503(self, client):
        # Raw connectivity failure (network not ready on wake). Transient.
        with patch.object(
            app_module.auth_ops_client.auth,
            "refresh_session",
            side_effect=ConnectionError("connection refused"),
        ):
            resp = client.post(REFRESH_URL, json=BODY)
        assert resp.status_code == 503

    def test_no_session_returns_401(self, client):
        # Response with no session is a genuine failure, not transient.
        with patch.object(
            app_module.auth_ops_client.auth,
            "refresh_session",
            return_value=SimpleNamespace(session=None),
        ):
            resp = client.post(REFRESH_URL, json=BODY)
        assert resp.status_code == 401
