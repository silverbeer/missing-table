"""The delegated token MT mints for an sb-agents chat turn (SB-1529): real tokens, fake profiles."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from auth import DELEGATED_AUDIENCE, AuthManager

pytestmark = [pytest.mark.unit, pytest.mark.backend]

JWT_SECRET = "session-secret-for-tests-0123456789abcdef"  # pragma: allowlist secret
SERVICE_SECRET = "service-secret-for-tests-0123456789abcdef"  # pragma: allowlist secret

PERSON = {"id": "person", "username": "fan", "role": "team-fan", "team_id": 19, "assigned_age_group_id": 15}
ADMIN = {"id": "boss", "username": "boss", "role": "admin"}
API = {"id": "api", "username": "ai_eval", "role": "team-fan", "is_api_account": True}


class FakeProfiles:
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
    return AuthManager(FakeProfiles(PERSON, ADMIN, API))


def test_a_minted_token_verifies_as_the_person_marked_delegated(manager):
    user = manager.verify_delegated_token(manager.create_delegated_token("person"))
    assert user["user_id"] == "person"
    assert (user["role"], user["team_id"], user["assigned_age_group_id"]) == ("team-fan", 19, 15)
    assert user["delegated"] is True


def test_it_lives_five_minutes(manager):
    payload = jwt.decode(
        manager.create_delegated_token("person"), SERVICE_SECRET, algorithms=["HS256"], audience=DELEGATED_AUDIENCE
    )
    assert payload["exp"] - payload["iat"] == 300
    assert payload["azp"] == "sb-agents"


def test_an_expired_token_is_refused(manager):
    assert manager.verify_delegated_token(manager.create_delegated_token("person", ttl_seconds=-1)) is None


def test_api_accounts_and_unknown_users_cannot_be_delegated(manager):
    assert manager.verify_delegated_token(manager.create_delegated_token("api")) is None
    assert manager.verify_delegated_token(manager.create_delegated_token("nobody")) is None


def test_it_works_nowhere_but_mt_mcp(manager):
    token = manager.create_delegated_token("person")
    assert manager.verify_ai_api_token(token) is None
    assert manager.verify_service_account_token(token) is None


def test_other_tokens_are_not_delegated_tokens(manager):
    assert manager.verify_delegated_token(manager.create_ai_api_token("api")) is None
    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    session = jwt.encode({"sub": "person", "aud": "authenticated", "exp": exp}, JWT_SECRET, algorithm="HS256")
    assert manager.verify_delegated_token(session) is None
    assert manager.verify_delegated_token("garbage") is None
