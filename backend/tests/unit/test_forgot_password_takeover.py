"""forgot-password no longer hands out other people's accounts (SB-1129).

The endpoint is unauthenticated, as it has to be. It used to accept an email
address for any account that had none on file, store it, and send a reset
link there — so one request naming a username was enough to take the account.
Eighteen accounts were exposed, two of them admin.

An address supplied in the request proves nothing about who is asking, so
there is no validation that would make the old behaviour safe. What replaces
it: use the verified address MT already holds, and otherwise say nothing
useful at all.
"""

import itertools
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

from models.auth import ForgotPasswordRequest

# forgot-password is rate limited to 3 per hour per IP, and the limiter keeps
# its state for the life of the process. A counter scoped to a test would
# restart and collide with the previous one, so every call in this module
# gets an address of its own — the limiter is not what any of this is
# testing.
_ips = itertools.count(1)


def next_ip():
    n = next(_ips)
    return f"198.51.{n // 254}.{n % 254 + 1}"


def make_request(ip):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/forgot-password",
            "headers": [(b"host", b"testserver")],
            "query_string": b"",
            "client": (ip, 1234),
            "app": __import__("app").app,
        }
    )


@pytest.fixture
def call():
    """Invoke the endpoint with the DAO, mailer and auth client stubbed."""
    import app as app_module

    async def _call(*, profile_email=None, auth_email=None, auth_raises=False, backfill_raises=False):
        user = {"id": "u-1", "username": "tom", "email": profile_email}
        mailer = MagicMock()
        mailer.send_password_reset.return_value = True

        auth_client = MagicMock()
        if backfill_raises:
            auth_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
                "duplicate key value violates unique constraint"
            )
        if auth_raises:
            auth_client.auth.admin.list_users.side_effect = Exception("supabase down")
        else:
            auth_client.auth.admin.list_users.return_value = (
                [MagicMock(id="u-1", email=auth_email)] if auth_email else []
            )

        with (
            patch.object(app_module.player_dao, "get_user_for_password_reset", return_value=user),
            patch.object(app_module.auth_manager, "create_password_reset_token", return_value="tok"),
            patch.object(app_module, "EmailService", return_value=mailer),
            patch.object(app_module, "auth_service_client", auth_client),
        ):
            response = await app_module.forgot_password(
                make_request(next_ip()), ForgotPasswordRequest(identifier="tom")
            )
        return response, mailer, auth_client

    return _call


class TestTheTakeoverIsClosed:
    def test_the_request_model_has_no_email_field(self):
        """Removed rather than validated, so nothing can reach for it."""
        assert "email" not in ForgotPasswordRequest.model_fields

    def test_an_email_in_the_body_is_rejected_outright(self):
        """Pydantic ignores unknown fields by default, so the belt-and-braces
        check is that it never reaches the profile — see below."""
        body = ForgotPasswordRequest(identifier="tom", email="attacker@example.com")
        assert not hasattr(body, "email")

    @pytest.mark.asyncio
    async def test_nothing_is_written_when_there_is_no_address(self, call):
        _, _, auth_client = await call(profile_email=None, auth_email=None)
        auth_client.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_reset_is_sent_when_there_is_no_address(self, call):
        _, mailer, _ = await call(profile_email=None, auth_email=None)
        mailer.send_password_reset.assert_not_called()


class TestTheResponseGivesNothingAway:
    @pytest.mark.asyncio
    async def test_all_three_outcomes_are_identical(self, call):
        """An unknown username, a reachable account and an unreachable one
        must be indistinguishable. `needs_email` used to confirm both that
        the account existed and that it was one of the vulnerable ones."""
        import app as app_module

        reachable, _, _ = await call(profile_email="parent@example.com")
        unreachable, _, _ = await call(profile_email=None, auth_email=None)

        with (
            patch.object(app_module.player_dao, "get_user_for_password_reset", return_value=None),
        ):
            unknown = await app_module.forgot_password(
                make_request(next_ip()), ForgotPasswordRequest(identifier="nobody")
            )

        assert reachable == unreachable == unknown

    @pytest.mark.asyncio
    async def test_needs_email_is_gone(self, call):
        response, _, _ = await call(profile_email=None, auth_email=None)
        assert "needs_email" not in response


class TestTheVerifiedAddressWeAlreadyHold:
    @pytest.mark.asyncio
    async def test_a_profile_address_is_used(self, call):
        _, mailer, _ = await call(profile_email="parent@example.com")
        assert mailer.send_password_reset.call_args[0][0] == "parent@example.com"

    @pytest.mark.asyncio
    async def test_an_auth_address_is_used_when_the_profile_has_none(self, call):
        """Four accounts — two of them Google sign-ins, where Google verified
        the address — had a real address on auth.users and null on the
        profile, so they looked unreachable while we knew how to reach them."""
        _, mailer, _ = await call(profile_email=None, auth_email="parent@example.com")
        assert mailer.send_password_reset.call_args[0][0] == "parent@example.com"

    @pytest.mark.asyncio
    async def test_the_profile_is_backfilled_from_it(self, call):
        _, _, auth_client = await call(profile_email=None, auth_email="parent@example.com")
        auth_client.table.return_value.update.assert_called_once_with({"email": "parent@example.com"})

    @pytest.mark.asyncio
    async def test_a_synthetic_sign_in_identity_is_never_used(self, call):
        """`.local` is reserved for mDNS: sending there reports success and
        delivers nothing."""
        _, mailer, auth_client = await call(profile_email=None, auth_email="tom@missingtable.local")
        mailer.send_password_reset.assert_not_called()
        auth_client.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_backfill_failure_does_not_deny_the_reset(self, call):
        """user_profiles.email is UNIQUE and the write can clash. That is not
        a reason to withhold someone's reset."""
        response, mailer, _ = await call(
            profile_email=None, auth_email="parent@example.com", backfill_raises=True
        )
        assert mailer.send_password_reset.called
        assert "if an account exists" in str(response).lower()

    @pytest.mark.asyncio
    async def test_an_auth_lookup_outage_falls_through_quietly(self, call):
        response, mailer, _ = await call(profile_email=None, auth_raises=True)
        mailer.send_password_reset.assert_not_called()
        assert "if an account exists" in str(response).lower()
