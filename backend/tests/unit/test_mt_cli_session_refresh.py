"""`mt` sessions outlive the one-hour access token (SB-1410).

Every command goes through `get_client()`. It refreshes a token near expiry
before the call, and the client refreshes once and retries on a 401 — so a
long Claude Code session never has to `mt login` again while the refresh token
is good. Rotated refresh tokens are saved to the session and the user's copy.
"""

from __future__ import annotations

import time

import httpx
import jwt
import pytest
import typer

import mt_cli
from api_client import AuthenticationError, MissingTableClient

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(mt_cli, "MT_CONFIG_FILE", tmp_path / ".mt-config")
    monkeypatch.setattr(mt_cli, "STATE_FILE", tmp_path / ".mt-cli-state.json")
    monkeypatch.setattr(mt_cli, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr(mt_cli, "_ENV_OVERRIDE", None)
    monkeypatch.delenv("APP_ENV", raising=False)
    (tmp_path / ".env.local").write_text("BACKEND_URL=http://localhost:8000\n")


def token(expires_in: int) -> str:
    return jwt.encode({"sub": "u1", "exp": int(time.time()) + expires_in}, "test-secret", algorithm="HS256")


NEW_TOKEN = token(3600)


def login(access: str, refresh: str | None = "r1") -> None:
    state = mt_cli.CLIState(access_token=access, refresh_token=refresh, username="tom")
    mt_cli.save_state(state)
    mt_cli.save_user_state(state)


@pytest.fixture
def refreshes(monkeypatch):
    """Record each proactive refresh; `fail` makes the refresh token dead."""
    calls = {"with": [], "fail": False}

    def refresh(self):
        calls["with"].append(self._refresh_token)
        if calls["fail"]:
            raise AuthenticationError("Refresh token expired")
        return {"access_token": NEW_TOKEN, "refresh_token": "r2"}

    monkeypatch.setattr(MissingTableClient, "refresh_access_token", refresh)
    return calls


def saved_tokens() -> tuple:
    state, user = mt_cli.load_state(), mt_cli.load_user_state("tom")
    return (state.access_token, state.refresh_token), (user.access_token, user.refresh_token)


class TestBeforeTheCall:
    def test_a_fresh_token_is_used_without_refreshing(self, refreshes):
        fresh = token(3600)
        login(fresh)

        client, _ = mt_cli.get_client()

        assert client._access_token == fresh
        assert refreshes["with"] == []

    @pytest.mark.parametrize("expires_in", [60, -60])
    def test_a_token_near_or_past_expiry_is_refreshed_and_saved_everywhere(self, refreshes, expires_in):
        login(token(expires_in))

        client, _ = mt_cli.get_client()

        assert client._access_token == NEW_TOKEN
        assert refreshes["with"] == ["r1"]
        assert saved_tokens() == ((NEW_TOKEN, "r2"), (NEW_TOKEN, "r2"))

    def test_the_rotated_refresh_token_is_the_one_used_next_time(self, refreshes):
        login(token(-60))
        mt_cli.get_client()
        mt_cli.save_state(mt_cli.load_state().model_copy(update={"access_token": token(-60)}))

        mt_cli.get_client()

        assert refreshes["with"] == ["r1", "r2"]

    def test_a_dead_refresh_token_says_log_in_again(self, refreshes, capsys):
        refreshes["fail"] = True
        login(token(-60))

        with pytest.raises(typer.Exit):
            mt_cli.get_client()

        out = capsys.readouterr().out
        assert "Session expired for local" in out
        assert "mt --env local login" in out

    def test_an_unreadable_token_goes_to_the_server_as_is(self, refreshes):
        login("not-a-jwt")

        client, _ = mt_cli.get_client()

        assert client._access_token == "not-a-jwt"
        assert refreshes["with"] == []


class TestOnA401:
    """The server can still refuse a token the clock says is good."""

    def _transport(self, seen):
        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.path, request.headers.get("authorization")))
            if request.url.path == "/api/auth/refresh":
                return httpx.Response(200, json={"access_token": NEW_TOKEN, "refresh_token": "r2"})
            if request.headers.get("authorization") == f"Bearer {NEW_TOKEN}":
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(401, json={"detail": "Invalid or expired token"})

        return httpx.MockTransport(handler)

    def _client(self, seen, on_refresh=None):
        client = MissingTableClient(base_url="http://test", access_token=token(1800))
        client._client = httpx.Client(transport=self._transport(seen))
        client._refresh_token = "r1"
        client.on_token_refresh = on_refresh
        return client

    def test_refreshes_once_and_retries(self):
        seen, persisted = [], []
        client = self._client(seen, on_refresh=persisted.append)

        assert client._request("GET", "/api/teams").json() == {"ok": True}
        assert [path for path, _ in seen] == ["/api/teams", "/api/auth/refresh", "/api/teams"]
        assert [(t["access_token"], t["refresh_token"]) for t in persisted] == [(NEW_TOKEN, "r2")]

    def test_without_opting_in_a_401_is_raised(self):
        seen = []
        client = self._client(seen, on_refresh=None)

        with pytest.raises(AuthenticationError):
            client._request("GET", "/api/teams")
        assert [path for path, _ in seen] == ["/api/teams"]

    def test_a_401_on_an_auth_endpoint_is_never_refreshed(self):
        seen, persisted = [], []
        client = self._client(seen, on_refresh=persisted.append)

        with pytest.raises(AuthenticationError):
            client._request("POST", "/api/auth/logout")
        assert persisted == []

    def test_get_client_saves_tokens_refreshed_on_a_401(self):
        login(token(1800))
        client, _ = mt_cli.get_client()
        seen = []
        client._client = httpx.Client(transport=self._transport(seen))

        client._request("GET", "/api/teams")

        assert saved_tokens() == ((NEW_TOKEN, "r2"), (NEW_TOKEN, "r2"))
