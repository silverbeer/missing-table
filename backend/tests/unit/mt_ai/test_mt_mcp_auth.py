"""mt_mcp.auth (SB-1302): which bearer tokens mt-mcp accepts, and as whom."""

import pytest
from mt_mcp_harness import FakeAuth

from mt_mcp.auth import CLAIM, MTTokenVerifier, Principal

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.fixture
def auth() -> FakeAuth:
    return FakeAuth()


@pytest.fixture
def verifier(auth: FakeAuth) -> MTTokenVerifier:
    return MTTokenVerifier(auth.verify_session, auth.verify_api_account)


async def test_a_session_token_carries_the_callers_profile(verifier):
    token = await verifier.verify_token("team-mgr")

    assert token is not None
    assert token.subject == "u-team"
    principal = Principal(**token.claims[CLAIM])
    assert (principal.role, principal.team_id, principal.club_id) == ("team-manager", 102, 11)
    assert principal.is_test is False


async def test_an_api_account_token_is_accepted(verifier):
    token = await verifier.verify_token("api")

    assert token is not None
    assert Principal(**token.claims[CLAIM]).is_api_account is True


async def test_test_users_keep_their_flag(verifier):
    token = await verifier.verify_token("test-fan")

    assert Principal(**token.claims[CLAIM]).is_test is True


@pytest.mark.parametrize("token", ["garbage", "", "service-account-jwt"])
async def test_anything_else_is_refused(verifier, token):
    """Service-account tokens resolve in neither check, so they are refused like garbage."""
    assert await verifier.verify_token(token) is None


async def test_a_profile_without_a_user_id_is_refused(auth):
    verifier = MTTokenVerifier(lambda t: {"role": "admin"}, auth.verify_api_account)

    assert await verifier.verify_token("x") is None


async def test_a_failing_lookup_refuses_rather_than_raises(auth, verifier):
    auth.explode = True

    assert await verifier.verify_token("admin") is None


def test_principal_round_trips_as_the_dict_auth_py_takes():
    user = {"user_id": 7, "role": "admin", "username": "tom", "team_id": None, "club_id": 3, "is_test": True}

    principal = Principal.from_user(user)

    assert principal.user_id == "7"
    assert principal.as_user()["role"] == "admin"
    assert principal.as_user()["is_test"] is True
