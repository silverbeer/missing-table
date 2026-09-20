"""The journey suite has to live inside the auth rate limits (SB-1092).

Login is 5 per minute and signup 3 per hour, both keyed on the client IP
(SB-640), and a whole run comes from one GitHub runner. The suite signed up six
users every run and logged in about seventeen times, so it burned the budget
before it finished: signup returned 422 for a missing email, everything after it
failed, and the cleanup step — a separate process that logged in again — got 429
at every phase and deleted nothing. Fixtures then piled up in production.

These cover the three rules that keep it inside the limits: sign in rather than
sign up, wait out a 429 instead of failing, and hand the token to the next
process rather than logging in again.
"""

import json
import time
from pathlib import Path

import pytest

from api_client.exceptions import AuthenticationError, RateLimitError
from tests.fixtures.tsc import TSCClient, TSCConfig, load_session, save_session, session_file

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def session_in_tmp(tmp_path, monkeypatch):
    """Keep every test's session file out of the repo and out of each other's way."""
    monkeypatch.setenv("TSC_SESSION_FILE", str(tmp_path / "session.json"))


class FakeAPI:
    """Just the client surface TSCClient.login and signup_with_invite touch."""

    def __init__(self, *, login_failures=(), existing_user=True):
        self.login_failures = list(login_failures)
        self.existing_user = existing_user
        self.login_calls = 0
        self.signup_calls = 0
        self.signup_kwargs: dict[str, object] = {}
        self._access_token = None

    def login(self, username, password):
        self.login_calls += 1
        if self.login_failures:
            raise self.login_failures.pop(0)
        if not self.existing_user:
            raise AuthenticationError("Invalid credentials", 401, {})
        self._access_token = f"token-for-{username}"
        return {"access_token": self._access_token}

    def signup(self, **kwargs):
        self.signup_calls += 1
        self.signup_kwargs = kwargs
        self._access_token = "token-for-new-user"
        return {"user": {"id": "user-1"}}

    def get_profile(self):
        return {"id": "user-1", "username": "tsc_ci_club_mgr"}


def _client(api):
    client = TSCClient(config=TSCConfig(prefix="tsc_ci_"))
    client._client = api
    return client


class TestLoginWaitsOutTheRateLimit:
    def test_a_429_is_retried_rather_than_failing_the_run(self):
        api = FakeAPI(login_failures=[RateLimitError("HTTP 429", 429, {})])
        waited: list[float] = []

        result = _client(api).login("tsc_ci_admin", "pw", sleep=waited.append)

        assert result["access_token"] == "token-for-tsc_ci_admin"
        assert api.login_calls == 2
        assert waited == [20]

    def test_it_gives_up_after_the_last_wait(self):
        api = FakeAPI(login_failures=[RateLimitError("HTTP 429", 429, {})] * 9)
        waited: list[float] = []

        with pytest.raises(RateLimitError):
            _client(api).login("tsc_ci_admin", "pw", sleep=waited.append)

        assert waited == list(TSCClient.LOGIN_RETRY_WAITS)
        assert api.login_calls == len(TSCClient.LOGIN_RETRY_WAITS) + 1

    def test_other_failures_are_not_retried(self):
        api = FakeAPI(login_failures=[AuthenticationError("bad password", 401, {})])

        with pytest.raises(AuthenticationError):
            _client(api).login("tsc_ci_admin", "pw", sleep=lambda _s: None)

        assert api.login_calls == 1


class TestAccountsArePersistent:
    def test_an_existing_user_is_signed_in_not_signed_up(self):
        # Signup is 3 per hour; a run needs six accounts, so an attempt that was
        # always going to say "already registered" is what spent the budget.
        api = FakeAPI(existing_user=True)

        result = _client(api).signup_with_invite("tsc_ci_club_mgr", "pw", "INVITE1")

        assert api.signup_calls == 0
        assert result["already_existed"] is True

    def test_the_first_run_still_creates_the_account(self):
        api = FakeAPI(existing_user=False)

        _client(api).signup_with_invite("tsc_ci_club_mgr", "pw", "INVITE1")

        assert api.signup_calls == 1

    def test_signup_sends_the_email_the_api_requires(self):
        # UserSignup.email has been required since 2026-03-24; omitting it is
        # what returned 422 on the first user of every run.
        api = FakeAPI(existing_user=False)

        _client(api).signup_with_invite("tsc_ci_club_mgr", "pw", "INVITE1")

        assert api.signup_kwargs["email"] == "tsc_ci_club_mgr@example.com"


class TestTheSessionIsHandedOn:
    def test_a_successful_login_saves_the_token(self):
        api = FakeAPI()

        client = _client(api)
        client.login("tsc_ci_admin", "pw")

        saved = load_session(client.config.base_url)
        assert saved is not None
        assert saved["token"] == "token-for-tsc_ci_admin"

    def test_cleanup_adopts_the_saved_token_without_logging_in(self):
        api = FakeAPI()
        client = _client(api)
        save_session("borrowed-token", "tom", client.config.base_url)

        username = client.adopt_saved_session()

        assert username == "tom"
        assert api._access_token == "borrowed-token"
        assert api.login_calls == 0

    def test_a_stale_token_is_not_adopted(self):
        client = _client(FakeAPI())
        path = session_file(client.config.base_url)
        path.write_text(json.dumps({"token": "old", "username": "tom", "saved_at": time.time() - 7200}))

        assert client.adopt_saved_session() is None

    def test_the_token_file_is_not_world_readable(self):
        client = _client(FakeAPI())
        save_session("secret-token", "tom", client.config.base_url)

        assert oct(Path(session_file(client.config.base_url)).stat().st_mode)[-3:] == "600"
