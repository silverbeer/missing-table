"""A refused email is recorded as a failure, never as a success (SB-1126).

Resend rejected every outbound email for months because the sending domain
was unverified, and the backend logged ``forgot_password_email_sent`` each
time. The observability said the opposite of what happened, which is why
nobody noticed that password resets, invitations and invite approvals had all
stopped.

The cause is that ``EmailService.send_*`` returns ``False`` on a refused send
rather than raising, so a caller's ``try/except`` catches only a missing API
key. These tests pin the two things that follow from that: the result has to
be checked, and the HTTP response must not change when it is.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestEmailServiceReportsFailure:
    """EmailService returns False and logs, rather than raising."""

    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        from services.email_service import EmailService

        return EmailService()

    def test_a_refused_send_returns_false(self, service):
        with patch("resend.Emails.send", side_effect=Exception("domain is not verified")):
            assert service.send_password_reset("parent@example.com", "tok", "check") is False

    def test_a_successful_send_returns_true(self, service):
        with patch("resend.Emails.send", return_value={"id": "abc"}):
            assert service.send_password_reset("parent@example.com", "tok", "check") is True

    def test_the_failure_is_logged_as_a_named_event(self, service, caplog):
        with patch("resend.Emails.send", side_effect=Exception("domain is not verified")):
            service.send_password_reset("parent@example.com", "tok", "check")

        record = next(r for r in caplog.records if r.message == "email_send_failed")
        assert record.email_kind == "password_reset"
        # The reason has to survive into the log, or the next outage is just
        # as opaque as this one was.
        assert "not verified" in record.error

    def test_the_recipient_is_masked(self, service, caplog):
        with patch("resend.Emails.send", side_effect=Exception("nope")):
            service.send_password_reset("parent@example.com", "tok", "check")

        record = next(r for r in caplog.records if r.message == "email_send_failed")
        assert record.recipient == "par***@example.com"
        assert "parent@example.com" not in str(record.__dict__)


class TestMaskHelper:
    def test_keeps_enough_to_correlate_a_report(self):
        from services.email_service import _mask

        assert _mask("silverbeer@zohomail.com") == "sil***@zohomail.com"

    def test_handles_nothing_and_nonsense(self):
        from services.email_service import _mask

        assert _mask(None) == "***"
        assert _mask("") == "***"
        assert _mask("not-an-address") == "***"


class TestForgotPasswordLogsTheTruth:
    """The endpoint's log follows the send; its response does not."""

    @pytest.fixture
    def send_reset(self):
        """Call the endpoint body with the DAO and mailer stubbed out."""
        import app as app_module

        # A distinct client IP per call: these tests are about what gets
        # logged, and sharing an IP makes the rate limiter — not the code
        # under test — decide the outcome once several calls run together.
        client_ips = iter(f"203.0.113.{n}" for n in range(1, 200))

        async def _call(*, send_returns=True, send_raises=None):
            user = {"id": "u-1", "username": "check", "email": "parent@example.com"}
            mailer = MagicMock()
            if send_raises:
                mailer.send_password_reset.side_effect = send_raises
            else:
                mailer.send_password_reset.return_value = send_returns

            # slowapi's rate limiter insists on a real starlette Request,
            # so a mock will not do.
            from starlette.requests import Request

            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/api/auth/forgot-password",
                    "headers": [(b"host", b"testserver")],
                    "query_string": b"",
                    "client": (next(client_ips), 1234),
                    "app": app_module.app,
                }
            )

            from models.auth import ForgotPasswordRequest

            with (
                patch.object(app_module.player_dao, "get_user_for_password_reset", return_value=user),
                patch.object(app_module.auth_manager, "create_password_reset_token", return_value="tok"),
                patch.object(app_module, "EmailService", return_value=mailer),
            ):
                return await app_module.forgot_password(
                    request, ForgotPasswordRequest(identifier="check")
                )

        return _call

    @pytest.mark.asyncio
    async def test_a_refused_send_is_not_logged_as_sent(self, send_reset, caplog):
        await send_reset(send_returns=False)

        assert "forgot_password_email_send_failed" in caplog.text
        assert "forgot_password_email_sent" not in caplog.text

    @pytest.mark.asyncio
    async def test_a_successful_send_is_logged_as_sent(self, send_reset, caplog):
        await send_reset(send_returns=True)

        assert "forgot_password_email_sent" in caplog.text

    @pytest.mark.asyncio
    async def test_the_response_is_generic_whether_or_not_the_send_worked(self, send_reset):
        """Anti-enumeration is not negotiable, and a provider outage is not
        the caller's business either. Only the log distinguishes the two."""
        ok = await send_reset(send_returns=True)
        refused = await send_reset(send_returns=False)
        raised = await send_reset(send_raises=Exception("no api key"))

        assert ok == refused == raised
        assert "if an account exists" in str(ok).lower()
