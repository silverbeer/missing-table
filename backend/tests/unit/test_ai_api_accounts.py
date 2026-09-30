"""API-only AI users (SB-1145): real tokens, a fake profile table.

The properties that matter: an API-account token works on /api/ai/* and is
rejected everywhere else; a service account gets a controlled 403 from MT AI,
not a 500; an API account can never hold a general session.
"""

import os
import stat
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import typer
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from auth import AI_API_AUDIENCE, AI_API_TOKEN_MAX_DAYS, AuthManager, get_ai_user, security
from mt_ai import api
from scripts import manage_ai_users as script

pytestmark = [pytest.mark.unit, pytest.mark.backend]

JWT_SECRET = "session-secret-for-tests-0123456789abcdef"  # pragma: allowlist secret
SERVICE_SECRET = "service-secret-for-tests-0123456789abcdef"  # pragma: allowlist secret

API_REAL = {"id": "api-real", "username": "ai-eval-real", "role": "team-fan", "is_test": False, "is_api_account": True}
API_TEST = {"id": "api-test", "username": "ai-eval-test", "role": "team-fan", "is_test": True, "is_api_account": True}
PERSON = {"id": "person", "username": "fan", "role": "team-fan", "is_test": False, "is_api_account": False}


class FakeProfiles:
    """Just enough of the supabase client for `table("user_profiles").select().eq("id", x).execute()`."""

    def __init__(self, *rows):
        self.rows = {r["id"]: r for r in rows}

    def table(self, _name):
        return self

    def select(self, *_):
        return self

    def eq(self, _column, value):
        self._id = value
        return self

    def execute(self):
        row = self.rows.get(self._id)
        return type("Response", (), {"data": [row] if row else []})()


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("SERVICE_ACCOUNT_SECRET", SERVICE_SECRET)
    return AuthManager(FakeProfiles(API_REAL, API_TEST, PERSON))


def bearer(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def session_token(user_id):
    """A Supabase-style HS256 session token."""
    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    return jwt.encode({"sub": user_id, "aud": "authenticated", "exp": exp}, JWT_SECRET, algorithm="HS256")


class TestAiApiToken:
    def test_resolves_to_the_api_account_with_its_test_visibility(self, manager):
        real = manager.verify_ai_api_token(manager.create_ai_api_token("api-real"))
        test = manager.verify_ai_api_token(manager.create_ai_api_token("api-test"))

        assert real["user_id"] == "api-real"
        assert real["role"] == "team-fan"
        assert real["is_api_account"] is True
        assert real["is_test"] is False
        assert test["is_test"] is True

    def test_carries_its_own_audience_and_a_short_expiry(self, manager):
        claims = jwt.decode(
            manager.create_ai_api_token("api-real", expires_days=7),
            SERVICE_SECRET,
            algorithms=["HS256"],
            audience=AI_API_AUDIENCE,
        )

        assert claims["exp"] - claims["iat"] == 7 * 86400

    @pytest.mark.parametrize("days", [0, -1, AI_API_TOKEN_MAX_DAYS + 1, 365])
    def test_cannot_be_minted_long_lived(self, manager, days):
        with pytest.raises(ValueError):
            manager.create_ai_api_token("api-real", expires_days=days)

    def test_is_rejected_by_every_other_endpoint(self, manager):
        token = manager.create_ai_api_token("api-real")

        assert manager.verify_token(token) is None
        assert manager.verify_service_account_token(token) is None
        with pytest.raises(HTTPException) as exc:
            manager.get_current_user(bearer(token))
        assert exc.value.status_code == 401

    def test_naming_a_person_is_rejected(self, manager):
        assert manager.verify_ai_api_token(manager.create_ai_api_token("person")) is None

    def test_naming_a_deleted_account_is_rejected(self, manager):
        assert manager.verify_ai_api_token(manager.create_ai_api_token("gone")) is None

    def test_expired_is_rejected(self, manager):
        past = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
        token = jwt.encode({"sub": "api-real", "aud": AI_API_AUDIENCE, "exp": past}, SERVICE_SECRET, algorithm="HS256")

        assert manager.verify_ai_api_token(token) is None

    def test_a_session_token_cannot_name_an_api_account(self, manager):
        assert manager.verify_token(session_token("api-real")) is None
        assert manager.verify_token(session_token("person"))["user_id"] == "person"


class TestGetAiUser:
    def test_accepts_a_person_and_an_api_account(self, manager):
        assert manager.get_ai_user(bearer(session_token("person")))["user_id"] == "person"
        assert manager.get_ai_user(bearer(manager.create_ai_api_token("api-test")))["user_id"] == "api-test"

    def test_a_service_account_is_a_controlled_403(self, manager):
        token = manager.create_service_account_token("match-scraper", ["manage_matches"])

        with pytest.raises(HTTPException) as exc:
            manager.get_ai_user(bearer(token))

        assert exc.value.status_code == 403

    def test_garbage_is_401(self, manager):
        with pytest.raises(HTTPException) as exc:
            manager.get_ai_user(bearer("not-a-jwt"))

        assert exc.value.status_code == 401


def test_chat_returns_403_for_a_service_account_end_to_end(manager, monkeypatch):
    """The SB-1145 bug: this was a KeyError and a 500."""
    monkeypatch.setenv("MT_AI_ENABLED", "true")
    monkeypatch.setenv("MT_AI_MODEL", "gemini-test")
    app = FastAPI()
    app.include_router(api.router)

    def real_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
        return manager.get_ai_user(credentials)

    app.dependency_overrides[get_ai_user] = real_auth
    app.dependency_overrides[api.get_chat_service] = lambda: pytest.fail("must not reach the service")
    token = manager.create_service_account_token("match-scraper", ["manage_matches"])

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/ai/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Service accounts cannot use MT AI."}


class TestScript:
    def test_eval_accounts_are_one_real_and_one_test_viewer(self):
        by_name = {a.username: a for a in script.AI_EVAL_ACCOUNTS}

        assert by_name["ai-eval-real"].is_test is False
        assert by_name["ai-eval-test"].is_test is True

    def test_ensure_creates_only_what_is_missing(self):
        assert [a.username for a in script.missing_accounts({"ai-eval-real"})] == ["ai-eval-test"]
        assert script.missing_accounts({"ai-eval-real", "ai-eval-test"}) == []

    def test_profile_row_is_a_non_admin_api_account(self):
        row = script.profile_row(script.AI_EVAL_ACCOUNTS[1])

        assert row["role"] != "admin"
        assert row["is_api_account"] is True
        assert row["is_test"] is True
        assert row["id"]

    def test_token_file_is_private(self, tmp_path):
        where = script.write_token("tok", str(tmp_path / "nested" / "ai.jwt"), stdout_is_tty=True)

        assert (tmp_path / "nested" / "ai.jwt").read_text() == "tok\n"
        assert stat.S_IMODE(os.stat(where).st_mode) == 0o600

    def test_refuses_to_print_a_token_to_a_terminal(self, capsys):
        with pytest.raises(typer.BadParameter):
            script.write_token("tok", "-", stdout_is_tty=True)

        assert "tok" not in capsys.readouterr().out

    def test_writes_to_redirected_stdout(self, capsys):
        script.write_token("tok", "-", stdout_is_tty=False)

        assert capsys.readouterr().out == "tok\n"
