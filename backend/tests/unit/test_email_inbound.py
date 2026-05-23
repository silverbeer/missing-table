"""Unit tests for the inbound-email primitives (SB-35 Phase 1).

Covers:
- pure helpers in services/email_inbound (sanitizer, subject parsers, verifier)
- resolve_thread with mock DAOs for all 4 fallback branches
- POST /api/webhooks/email/inbound endpoint with verify + resend SDK + DAOs mocked

No database. Integration tests against real Supabase land later.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("EMAIL_INBOUND_WEBHOOK_SECRET", raising=False)
    yield


# ── pure helpers ─────────────────────────────────────────────────────────────


class TestParseCaseNumber:
    def test_basic_bracketed(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("[MT-42] Question") == 42

    def test_with_reply_prefix(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("Re: [MT-1042] My team") == 1042

    def test_lowercase_mt(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("[mt-7] x") == 7

    def test_extra_whitespace(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("[ MT-9 ] thing") == 9

    def test_unbracketed_returns_none(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("MT-99 in the wild") is None

    def test_none_input(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject(None) is None

    def test_empty_string(self):
        from services.email_inbound import parse_case_number_from_subject
        assert parse_case_number_from_subject("") is None


class TestNormalizeSubject:
    def test_strips_chained_reply_prefixes(self):
        from services.email_inbound import normalize_subject
        assert normalize_subject("Re: Re: RE:  Hello world") == "hello world"

    def test_strips_fwd_variants(self):
        from services.email_inbound import normalize_subject
        assert normalize_subject("Fwd: Fw: Fwd:  Hello") == "hello"

    def test_strips_case_number_token(self):
        from services.email_inbound import normalize_subject
        assert normalize_subject("Re: [MT-42] My Question") == "my question"

    def test_collapses_whitespace(self):
        from services.email_inbound import normalize_subject
        assert normalize_subject("  Hello    world  ") == "hello world"

    def test_none_returns_empty(self):
        from services.email_inbound import normalize_subject
        assert normalize_subject(None) == ""


class TestSanitizeHtml:
    def test_strips_script_tag(self):
        from services.email_inbound import sanitize_html
        # bleach strips tag but keeps inner text — that text is harmless
        # since no <script> tag reaches the rendered DOM.
        assert sanitize_html("<script>alert(1)</script><p>ok</p>") == "alert(1)<p>ok</p>"

    def test_keeps_allowed_tags(self):
        from services.email_inbound import sanitize_html
        result = sanitize_html("<p><strong>Hi</strong> <em>there</em></p>")
        assert result == "<p><strong>Hi</strong> <em>there</em></p>"

    def test_strips_javascript_href(self):
        from services.email_inbound import sanitize_html
        assert sanitize_html('<a href="javascript:alert(1)">x</a>') == "<a>x</a>"

    def test_preserves_https_href(self):
        from services.email_inbound import sanitize_html
        assert (
            sanitize_html('<a href="https://example.com">x</a>')
            == '<a href="https://example.com">x</a>'
        )

    def test_preserves_mailto(self):
        from services.email_inbound import sanitize_html
        assert (
            sanitize_html('<a href="mailto:a@b.com">a</a>')
            == '<a href="mailto:a@b.com">a</a>'
        )

    def test_strips_img_tag(self):
        # Not on our allowlist — should be removed (inner text kept, but img has none)
        from services.email_inbound import sanitize_html
        assert sanitize_html('<img src="x.png" alt="x">') == ""

    def test_none_passthrough(self):
        from services.email_inbound import sanitize_html
        assert sanitize_html(None) is None


class TestVerifyWebhook:
    def test_missing_secret_raises(self):
        from services.email_inbound import WebhookVerificationError, verify_webhook
        with pytest.raises(WebhookVerificationError, match="not configured"):
            verify_webhook(payload="{}", headers={})

    def test_missing_headers_raises(self, monkeypatch):
        from services.email_inbound import WebhookVerificationError, verify_webhook
        monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_test")
        with pytest.raises(WebhookVerificationError, match="Missing required webhook header"):
            verify_webhook(payload="{}", headers={"svix-id": "x"})

    def test_bad_signature_raises(self, monkeypatch):
        from services.email_inbound import WebhookVerificationError, verify_webhook
        monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_dGVzdA==")
        with pytest.raises(WebhookVerificationError):
            verify_webhook(
                payload="{}",
                headers={
                    "svix-id": "msg_test",
                    "svix-timestamp": "1700000000",
                    "svix-signature": "v1,not-a-real-signature",
                },
            )

    def test_passes_short_keys_to_svix_verify(self, monkeypatch):
        """Regression: Resend's WebhookHeaders TypedDict uses short keys
        ('id', 'timestamp', 'signature'), not the HTTP header names. Earlier
        code passed the prefixed names through and got 'svix-id header is
        required' failures in prod. Lock that mapping in."""
        from unittest.mock import patch

        from services.email_inbound import verify_webhook
        monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_test")

        with patch("services.email_inbound.resend.Webhooks.verify") as mock_verify:
            verify_webhook(
                payload='{"hello": "world"}',
                headers={
                    "Svix-Id": "msg_xyz",
                    "Svix-Timestamp": "1700000000",
                    "Svix-Signature": "v1,abc",
                    # Extra noise headers that should be dropped:
                    "content-type": "application/json",
                    "x-trace": "trace-123",
                },
            )

        mock_verify.assert_called_once()
        options = mock_verify.call_args.args[0]
        # Short keys, not prefixed.
        assert options["headers"] == {
            "id": "msg_xyz",
            "timestamp": "1700000000",
            "signature": "v1,abc",
        }
        assert options["payload"] == '{"hello": "world"}'
        assert options["webhook_secret"] == "whsec_test"


# ── resolve_thread ───────────────────────────────────────────────────────────


def _make_threads_dao(*, by_case_number=None, by_id=None, recent=None, created=None):
    dao = MagicMock()
    dao.get_by_case_number.return_value = by_case_number
    dao.get_thread_by_id.return_value = by_id
    dao.find_recent_by_participant.return_value = recent or []
    dao.create_for_inbound.return_value = created or {
        "id": "new-uuid",
        "case_number": 99,
        "subject": "",
        "status": "new",
    }
    return dao


def _make_messages_dao(*, thread_id_for_in_reply_to=None):
    dao = MagicMock()
    dao.find_thread_id_by_in_reply_to.return_value = thread_id_for_in_reply_to
    return dao


class TestResolveThread:
    def test_in_reply_to_match_returns_existing_thread(self):
        from services.email_inbound import resolve_thread
        target = {"id": "t1", "case_number": 10, "subject": "Original", "status": "awaiting_user"}
        threads = _make_threads_dao(by_id=target)
        messages = _make_messages_dao(thread_id_for_in_reply_to="t1")

        thread, created = resolve_thread(
            threads, messages,
            subject="Re: Original",
            from_email="x@y.com",
            from_name=None,
            in_reply_to="msg-abc",
        )
        assert thread is target
        assert created is False
        threads.create_for_inbound.assert_not_called()

    def test_case_number_match_when_in_reply_to_missing(self):
        from services.email_inbound import resolve_thread
        target = {"id": "t2", "case_number": 42, "subject": "Old", "status": "resolved"}
        threads = _make_threads_dao(by_case_number=target)
        messages = _make_messages_dao(thread_id_for_in_reply_to=None)

        thread, created = resolve_thread(
            threads, messages,
            subject="Re: [MT-42] Old",
            from_email="x@y.com",
            from_name=None,
            in_reply_to=None,
        )
        assert thread is target
        assert created is False
        threads.create_for_inbound.assert_not_called()

    def test_case_number_in_subject_overrides_unrelated_in_reply_to(self):
        # If In-Reply-To points at a deleted/unknown message, we should fall
        # through to the [MT-{n}] subject token rather than start a new thread.
        from services.email_inbound import resolve_thread
        target = {"id": "t3", "case_number": 7, "subject": "Old", "status": "new"}
        threads = _make_threads_dao(by_case_number=target)
        messages = _make_messages_dao(thread_id_for_in_reply_to=None)  # unknown

        thread, _created = resolve_thread(
            threads, messages,
            subject="Re: [MT-7] Old",
            from_email="x@y.com",
            from_name=None,
            in_reply_to="msg-unknown",
        )
        assert thread is target

    def test_participant_subject_fallback(self):
        from services.email_inbound import resolve_thread
        target = {"id": "t4", "case_number": 5, "subject": "Hello world", "status": "awaiting_user"}
        # No In-Reply-To, no [MT-] in subject — must match by participant + subject
        threads = _make_threads_dao(recent=[target])
        messages = _make_messages_dao()

        thread, created = resolve_thread(
            threads, messages,
            subject="Re: Hello world",
            from_email="x@y.com",
            from_name=None,
            in_reply_to=None,
        )
        assert thread is target
        assert created is False
        threads.create_for_inbound.assert_not_called()

    def test_creates_new_thread_when_no_match(self):
        from services.email_inbound import resolve_thread
        threads = _make_threads_dao(
            created={"id": "fresh", "case_number": 101, "subject": "Brand new", "status": "new"}
        )
        messages = _make_messages_dao()

        thread, created = resolve_thread(
            threads, messages,
            subject="Brand new",
            from_email="x@y.com",
            from_name="X Y",
            in_reply_to=None,
        )
        assert created is True
        assert thread["case_number"] == 101
        threads.create_for_inbound.assert_called_once()


# ── webhook endpoint ─────────────────────────────────────────────────────────


@pytest.fixture
def webhook_client(monkeypatch):
    """A fresh FastAPI app with only the email-inbound router mounted, so
    we don't pull in the full backend (auth middleware, Supabase, etc.)
    just to exercise this one endpoint."""
    monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_test")
    from api import webhooks_email
    app = FastAPI()
    app.include_router(webhooks_email.router)
    return TestClient(app), webhooks_email


class TestWebhookEndpoint:
    def test_signature_rejected(self, webhook_client):
        client, _ = webhook_client
        with patch(
            "api.webhooks_email.verify_webhook",
            side_effect=__import__("services.email_inbound", fromlist=["WebhookVerificationError"])
                .WebhookVerificationError("bad sig"),
        ):
            resp = client.post(
                "/api/webhooks/email/inbound",
                content=b"{}",
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 401

    def test_unknown_event_type_returns_ignored(self, webhook_client):
        client, _ = webhook_client
        with patch("api.webhooks_email.verify_webhook"):
            resp = client.post(
                "/api/webhooks/email/inbound",
                content=json.dumps({"type": "email.delivered", "data": {}}).encode(),
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_missing_email_id_returns_400(self, webhook_client):
        client, _ = webhook_client
        with patch("api.webhooks_email.verify_webhook"):
            resp = client.post(
                "/api/webhooks/email/inbound",
                content=json.dumps({"type": "email.received", "data": {}}).encode(),
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 400

    def test_happy_path_new_thread(self, webhook_client):
        client, module = webhook_client
        received_email = {
            "from": '"Jane Doe" <jane@example.com>',
            "to": ["support@missingtable.com"],
            "subject": "Help with my invite",
            "message_id": "<msg-001@example.com>",
            "html": "<p>Hi support</p>",
            "text": "Hi support",
            "headers": {},
            "attachments": [],
            "created_at": "2026-05-23T12:00:00Z",
        }
        new_thread = {
            "id": "thread-uuid",
            "case_number": 1,
            "subject": "Help with my invite",
            "status": "new",
        }

        with (
            patch("api.webhooks_email.verify_webhook"),
            patch("api.webhooks_email.resend.Emails.Receiving.get", return_value=received_email),
            patch.object(module._messages_dao, "find_by_message_id", return_value=None),
            patch.object(module._messages_dao, "insert_inbound") as insert,
            patch("api.webhooks_email.resolve_thread", return_value=(new_thread, True)) as resolver,
            patch.object(module._threads_dao, "transition_on_inbound") as transition,
        ):
            resp = client.post(
                "/api/webhooks/email/inbound",
                content=json.dumps(
                    {"type": "email.received", "data": {"email_id": "em-123"}}
                ).encode(),
                headers={"content-type": "application/json"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["case_number"] == 1
        assert body["created_new_thread"] is True

        # message_id stored without angle brackets
        insert_kwargs = insert.call_args.kwargs
        assert insert_kwargs["message_id"] == "msg-001@example.com"
        assert insert_kwargs["from_email"] == "jane@example.com"
        assert insert_kwargs["from_name"] == "Jane Doe"
        assert insert_kwargs["had_attachments"] is False

        # New thread → no transition (create_for_inbound already set status='new')
        transition.assert_not_called()
        resolver.assert_called_once()

    def test_idempotent_duplicate_message_id(self, webhook_client):
        client, module = webhook_client
        existing = {"id": "msg-row", "thread_id": "thread-uuid", "message_id": "msg-001@example.com"}
        received_email = {
            "from": "jane@example.com",
            "to": ["support@missingtable.com"],
            "subject": "Help",
            "message_id": "<msg-001@example.com>",
            "html": None,
            "text": "Hi",
            "headers": {},
            "attachments": [],
            "created_at": "2026-05-23T12:00:00Z",
        }

        with (
            patch("api.webhooks_email.verify_webhook"),
            patch("api.webhooks_email.resend.Emails.Receiving.get", return_value=received_email),
            patch.object(module._messages_dao, "find_by_message_id", return_value=existing),
            patch.object(module._messages_dao, "insert_inbound") as insert,
        ):
            resp = client.post(
                "/api/webhooks/email/inbound",
                content=json.dumps(
                    {"type": "email.received", "data": {"email_id": "em-123"}}
                ).encode(),
                headers={"content-type": "application/json"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "duplicate"
        insert.assert_not_called()

    def test_attachments_flag_set_but_attachments_not_stored(self, webhook_client):
        client, module = webhook_client
        received_email = {
            "from": "jane@example.com",
            "to": ["support@missingtable.com"],
            "subject": "Help",
            "message_id": "<msg-att@example.com>",
            "html": "<p>see attached</p>",
            "text": "see attached",
            "headers": {},
            "attachments": [{"filename": "secret.pdf", "content": "BIGBASE64..."}],
            "created_at": "2026-05-23T12:00:00Z",
        }
        new_thread = {"id": "t", "case_number": 2, "subject": "Help", "status": "new"}

        with (
            patch("api.webhooks_email.verify_webhook"),
            patch("api.webhooks_email.resend.Emails.Receiving.get", return_value=received_email),
            patch.object(module._messages_dao, "find_by_message_id", return_value=None),
            patch.object(module._messages_dao, "insert_inbound") as insert,
            patch("api.webhooks_email.resolve_thread", return_value=(new_thread, True)),
        ):
            client.post(
                "/api/webhooks/email/inbound",
                content=json.dumps(
                    {"type": "email.received", "data": {"email_id": "em-att"}}
                ).encode(),
                headers={"content-type": "application/json"},
            )

        insert_kwargs = insert.call_args.kwargs
        assert insert_kwargs["had_attachments"] is True
        # raw_payload must not include the attachment bodies
        assert "attachments" not in insert_kwargs["raw_payload"]
