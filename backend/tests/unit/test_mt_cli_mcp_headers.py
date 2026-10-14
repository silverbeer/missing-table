"""`mt mcp headers` (SB-1304): Claude Code's headersHelper for mt-mcp.

Claude Code runs the helper on each connection and again after a 401/403, and
reads its stdout as a JSON object of headers. So stdout must be that object and
nothing else, and a token near expiry is refreshed before it is handed over.
"""

from __future__ import annotations

import json
import time

import jwt
import pytest
from typer.testing import CliRunner

import mt_cli
from api_client import AuthenticationError

pytestmark = [pytest.mark.unit]

runner = CliRunner()


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


def save(access: str | None, refresh: str | None = "r1") -> None:
    mt_cli.save_state(mt_cli.CLIState(access_token=access, refresh_token=refresh, username="tom"))


class FakeClient:
    refreshed_with: list[str | None] = []
    fail = False

    def __init__(self, base_url, access_token=None):
        self._refresh_token = None

    def refresh_access_token(self):
        FakeClient.refreshed_with.append(self._refresh_token)
        if FakeClient.fail:
            raise AuthenticationError("Refresh token expired")
        return {"access_token": NEW_TOKEN, "refresh_token": "r2"}

    def close(self):
        pass


NEW_TOKEN = token(3600)


@pytest.fixture
def client(monkeypatch):
    FakeClient.refreshed_with = []
    FakeClient.fail = False
    monkeypatch.setattr(mt_cli, "MissingTableClient", FakeClient)
    return FakeClient


def test_a_fresh_token_is_printed_as_json_headers_and_nothing_else(client):
    fresh = token(3600)
    save(fresh)

    result = runner.invoke(mt_cli.app, ["mcp", "headers"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"Authorization": f"Bearer {fresh}", "X-MT-Client": "claude-code"}
    assert client.refreshed_with == []


@pytest.mark.parametrize("expires_in", [60, -60])
def test_a_token_near_or_past_expiry_is_refreshed_and_saved(client, expires_in):
    save(token(expires_in))

    result = runner.invoke(mt_cli.app, ["mcp", "headers"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["Authorization"] == f"Bearer {NEW_TOKEN}"
    assert client.refreshed_with == ["r1"]
    state = mt_cli.load_state()
    assert (state.access_token, state.refresh_token) == (NEW_TOKEN, "r2")


def test_an_unreadable_token_is_refreshed_rather_than_trusted(client):
    save("not-a-jwt")

    result = runner.invoke(mt_cli.app, ["mcp", "headers"])

    assert result.exit_code == 0
    assert client.refreshed_with == ["r1"]


def test_not_logged_in_fails_with_nothing_on_stdout(client):
    save(None)

    result = runner.invoke(mt_cli.app, ["mcp", "headers"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "mt login" in result.stderr


def test_a_failed_refresh_fails_with_nothing_on_stdout(client):
    client.fail = True
    save(token(10))

    result = runner.invoke(mt_cli.app, ["mcp", "headers"])

    assert result.exit_code == 1
    assert result.stdout == ""


# --- --user: one Claude Code server per role (SB-1331) ---


def login_as(username: str, access: str, refresh: str) -> None:
    """What `mt login <username>` stores: the environment's session and the user's."""
    state = mt_cli.CLIState(access_token=access, refresh_token=refresh, username=username)
    mt_cli.save_state(state)
    mt_cli.save_user_state(state)


def bearer(result) -> str:
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)["Authorization"]


def test_each_user_keeps_their_own_session_after_another_logs_in(client):
    tom, club, player = token(3600), token(3601), token(3602)
    login_as("tom", tom, "r-tom")
    login_as("tom_club", club, "r-club")
    login_as("gabe35", player, "r-gabe")

    assert bearer(runner.invoke(mt_cli.app, ["mcp", "headers", "--user", "tom"])) == f"Bearer {tom}"
    assert bearer(runner.invoke(mt_cli.app, ["mcp", "headers", "--user", "tom_club"])) == f"Bearer {club}"
    assert bearer(runner.invoke(mt_cli.app, ["mcp", "headers", "-u", "gabe35"])) == f"Bearer {player}"
    # Without --user: whoever logged in last, as before.
    assert bearer(runner.invoke(mt_cli.app, ["mcp", "headers"])) == f"Bearer {player}"
    assert client.refreshed_with == []


def test_a_refreshed_user_token_is_saved_for_that_user_only(client):
    login_as("tom", token(3600), "r-tom")
    login_as("tom_club", token(10), "r-club")

    result = runner.invoke(mt_cli.app, ["mcp", "headers", "--user", "tom_club"])

    assert bearer(result) == f"Bearer {NEW_TOKEN}"
    assert client.refreshed_with == ["r-club"]
    assert mt_cli.load_user_state("tom_club").refresh_token == "r2"
    assert mt_cli.load_user_state("tom").refresh_token == "r-tom"
    # The environment's session (tom_club, logged in last) is not rewritten by --user.
    assert mt_cli.load_state().refresh_token == "r-club"


def test_a_login_from_before_per_user_storage_still_serves_its_user(client):
    fresh = token(3600)
    save(fresh)  # environment session only, username "tom"

    assert bearer(runner.invoke(mt_cli.app, ["mcp", "headers", "--user", "tom"])) == f"Bearer {fresh}"


def test_a_user_who_never_logged_in_fails_naming_them(client):
    save(token(3600))

    result = runner.invoke(mt_cli.app, ["mcp", "headers", "--user", "gabe35"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "mt login gabe35" in result.stderr


def test_user_sessions_are_per_environment(client, tmp_path):
    (tmp_path / ".env.prod").write_text("BACKEND_URL=https://api.example.test\n")
    login_as("tom_club", token(3600), "r-local")

    result = runner.invoke(mt_cli.app, ["--env", "prod", "mcp", "headers", "--user", "tom_club"])

    assert result.exit_code == 1
    assert result.stdout == ""
