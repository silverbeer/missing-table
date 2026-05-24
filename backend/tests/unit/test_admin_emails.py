"""Unit tests for the Support Inbox admin API (SB-35 Phase 2).

Covers:
- pure helpers in services/email_outbound (subject prefix, references, message-id)
- send_admin_reply orchestrator with mocked DAOs + resend
- /api/admin/emails/* endpoints with require_admin overridden + DAOs patched

No database. Integration tests against real Supabase land later.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("EMAIL_INBOUND_WEBHOOK_SECRET", raising=False)
    yield


# ── Pure helpers: prefix_subject_with_case_number ────────────────────────────


class TestPrefixSubjectWithCaseNumber:
    def test_no_token_adds_re_and_prefix(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert prefix_subject_with_case_number("My Question", 1) == "Re: [MT-1] My Question"

    def test_strips_single_re_then_adds(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert prefix_subject_with_case_number("Re: My Question", 7) == "Re: [MT-7] My Question"

    def test_strips_chained_re_then_adds(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert (
            prefix_subject_with_case_number("Re: Re: Fwd: Hello", 42)
            == "Re: [MT-42] Hello"
        )

    def test_already_has_token_and_re_is_unchanged(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert (
            prefix_subject_with_case_number("Re: [MT-1] My Question", 1)
            == "Re: [MT-1] My Question"
        )

    def test_already_has_token_no_re_adds_re(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert (
            prefix_subject_with_case_number("[MT-1] My Question", 1)
            == "Re: [MT-1] My Question"
        )

    def test_double_re_with_token_unchanged(self):
        # The brief's "don't double-prefix on Re: Re: [MT-1]" case.
        from services.email_outbound import prefix_subject_with_case_number
        assert (
            prefix_subject_with_case_number("Re: Re: [MT-1] My Question", 1)
            == "Re: Re: [MT-1] My Question"
        )

    def test_calling_twice_is_idempotent(self):
        from services.email_outbound import prefix_subject_with_case_number
        once = prefix_subject_with_case_number("My Question", 5)
        twice = prefix_subject_with_case_number(once, 5)
        assert once == twice

    def test_empty_subject_becomes_no_subject(self):
        from services.email_outbound import prefix_subject_with_case_number
        assert prefix_subject_with_case_number("", 9) == "Re: [MT-9] (no subject)"

    def test_lowercase_token_match_idempotent(self):
        from services.email_outbound import prefix_subject_with_case_number
        # Case-insensitive on MT, but our prefix output is canonical [MT-1].
        assert (
            prefix_subject_with_case_number("Re: [mt-1] My Question", 1)
            == "Re: [mt-1] My Question"
        )


# ── Pure helpers: generate_message_id ────────────────────────────────────────


class TestGenerateMessageId:
    def test_format(self):
        from services.email_outbound import generate_message_id
        mid = generate_message_id()
        assert mid.startswith("mt-")
        assert mid.endswith("@missingtable.com")
        # No angle brackets in returned value.
        assert "<" not in mid and ">" not in mid

    def test_uniqueness(self):
        from services.email_outbound import generate_message_id
        a, b = generate_message_id(), generate_message_id()
        assert a != b


# ── Pure helpers: build_references ───────────────────────────────────────────


class TestBuildReferences:
    def test_empty_inputs_returns_empty_string(self):
        from services.email_outbound import build_references
        assert build_references(None, None) == ""
        assert build_references("", None) == ""

    def test_appends_in_reply_to_bracketed(self):
        from services.email_outbound import build_references
        # in_reply_to is the stripped form; helper brackets it for storage.
        result = build_references("<a@x> <b@x>", "c@x")
        assert result == "<a@x> <b@x> <c@x>"

    def test_dedupe_when_already_present(self):
        from services.email_outbound import build_references
        result = build_references("<a@x> <b@x>", "b@x")
        # The bracketed form <b@x> is already in the chain.
        assert result == "<a@x> <b@x>"

    def test_no_existing_references_just_brackets_new(self):
        from services.email_outbound import build_references
        assert build_references(None, "lonely@x") == "<lonely@x>"


# ── send_admin_reply orchestrator ────────────────────────────────────────────


def _thread(case_number: int = 1, **overrides):
    base = {
        "id": "thread-uuid",
        "case_number": case_number,
        "subject": "My Question",
        "participant_email": "jane@example.com",
        "status": "awaiting_admin",
    }
    base.update(overrides)
    return base


class TestSendAdminReply:
    def _make_daos(self, latest_inbound=None):
        threads = MagicMock()
        messages = MagicMock()
        messages.get_latest_inbound_for_thread.return_value = latest_inbound
        messages.insert_outbound.return_value = {
            "id": "msg-row", "direction": "outbound"
        }
        threads.transition_on_outbound.return_value = _thread(status="awaiting_user")
        return threads, messages

    def test_sets_in_reply_to_and_references_headers(self, monkeypatch):
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        latest = {
            "message_id": "user-msg-1@example.com",
            "references": "<orig@example.com> <user-msg-1@example.com>",
        }
        threads, messages = self._make_daos(latest_inbound=latest)

        with patch.object(email_outbound.resend.Emails, "send") as mock_send:
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(),
                body_text="Hi Jane, here's an answer.",
                body_html=None,
                admin_user_id="admin-1",
            )

        kwargs_payload = mock_send.call_args.args[0]
        headers = kwargs_payload["headers"]
        assert headers["In-Reply-To"] == "<user-msg-1@example.com>"
        # References already contained <user-msg-1@example.com> → not re-appended.
        assert headers["References"] == "<orig@example.com> <user-msg-1@example.com>"
        assert headers["Message-ID"].startswith("<mt-")
        assert headers["Message-ID"].endswith("@missingtable.com>")

    def test_subject_prefixed_with_case_number(self, monkeypatch):
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        threads, messages = self._make_daos(
            latest_inbound={"message_id": "u@x", "references": None}
        )

        with patch.object(email_outbound.resend.Emails, "send") as mock_send:
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(case_number=42),
                body_text="answer",
                body_html=None,
                admin_user_id="admin-1",
            )

        payload = mock_send.call_args.args[0]
        assert payload["subject"] == "Re: [MT-42] My Question"
        assert payload["from"] == "support@contact.missingtable.com"
        assert payload["to"] == ["jane@example.com"]

    def test_subject_prefix_idempotent_on_already_prefixed_thread(self, monkeypatch):
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        threads, messages = self._make_daos(
            latest_inbound={"message_id": "u@x", "references": None}
        )

        with patch.object(email_outbound.resend.Emails, "send") as mock_send:
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(case_number=1, subject="Re: [MT-1] My Question"),
                body_text="answer",
                body_html=None,
                admin_user_id="admin-1",
            )

        assert mock_send.call_args.args[0]["subject"] == "Re: [MT-1] My Question"

    def test_persists_outbound_with_stripped_message_id(self, monkeypatch):
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        threads, messages = self._make_daos(
            latest_inbound={"message_id": "u@x", "references": None}
        )

        with patch.object(email_outbound.resend.Emails, "send"):
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(),
                body_text="answer",
                body_html="<p>answer</p>",
                admin_user_id="admin-1",
            )

        ins = messages.insert_outbound.call_args.kwargs
        # Stored without angle brackets (parity with inbound storage).
        assert ins["message_id"].startswith("mt-")
        assert ins["message_id"].endswith("@missingtable.com")
        assert "<" not in ins["message_id"]
        # In-Reply-To is the bare (stripped) inbound message_id.
        assert ins["in_reply_to"] == "u@x"
        assert ins["sent_by_user_id"] == "admin-1"
        assert ins["body_html"] == "<p>answer</p>"
        assert ins["from_email"] == "support@contact.missingtable.com"

    def test_transitions_thread_to_awaiting_user(self, monkeypatch):
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        threads, messages = self._make_daos(
            latest_inbound={"message_id": "u@x", "references": None}
        )

        with patch.object(email_outbound.resend.Emails, "send"):
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(),
                body_text="answer",
                body_html=None,
                admin_user_id="admin-1",
            )

        threads.transition_on_outbound.assert_called_once()
        kwargs = threads.transition_on_outbound.call_args.kwargs
        assert kwargs["last_message_at"]  # ISO timestamp string

    def test_ensures_resend_api_key_before_send(self, monkeypatch):
        """Regression: lesson #2 from Phase 1 applies to the outbound path too.
        On a fresh pod, resend.api_key may still be None when an admin clicks
        Reply. Verify the orchestrator sets it from the env var so Emails.send
        doesn't fail with ValidationError('API key is invalid')."""
        import resend as resend_mod
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test_outbound_set")

        original = resend_mod.api_key
        resend_mod.api_key = None
        try:
            threads, messages = self._make_daos(
                latest_inbound={"message_id": "u@x", "references": None}
            )
            with patch.object(email_outbound.resend.Emails, "send"):
                email_outbound.send_admin_reply(
                    threads, messages,
                    thread=_thread(),
                    body_text="answer",
                    body_html=None,
                    admin_user_id="admin-1",
                )
            assert resend_mod.api_key == "re_test_outbound_set"
        finally:
            resend_mod.api_key = original

    def test_no_inbound_yet_still_sends_without_in_reply_to(self, monkeypatch):
        # Admin starts a thread before any inbound exists — shouldn't crash.
        from services import email_outbound
        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        threads, messages = self._make_daos(latest_inbound=None)

        with patch.object(email_outbound.resend.Emails, "send") as mock_send:
            email_outbound.send_admin_reply(
                threads, messages,
                thread=_thread(),
                body_text="answer",
                body_html=None,
                admin_user_id="admin-1",
            )

        headers = mock_send.call_args.args[0]["headers"]
        assert "In-Reply-To" not in headers
        # References can be empty / omitted.
        assert headers.get("References", "") == ""


# ── Endpoint tests ───────────────────────────────────────────────────────────


@pytest.fixture
def admin_client():
    """Minimal FastAPI app with the admin_emails router and require_admin
    overridden to a stub admin user. The module-level DAO singletons are
    accessible via `module._threads_dao` / `module._messages_dao` so each
    test can patch their methods."""
    from api import admin_emails
    from auth import require_admin

    app = FastAPI()
    app.include_router(admin_emails.router)
    app.dependency_overrides[require_admin] = lambda: {
        "id": "admin-user-1", "role": "admin", "username": "admin"
    }
    return TestClient(app), admin_emails


class TestListThreadsEndpoint:
    def test_default_status_filter_applied(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._threads_dao, "list_by_status",
            return_value={"items": [], "next_cursor": None},
        ) as mock_list:
            resp = client.get("/api/admin/emails/threads")
        assert resp.status_code == 200
        args, kwargs = mock_list.call_args
        assert args[0] == ["new", "awaiting_admin"]
        assert kwargs["limit"] == 50
        assert kwargs["cursor"] is None

    def test_status_csv_parsed(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._threads_dao, "list_by_status",
            return_value={"items": [], "next_cursor": None},
        ) as mock_list:
            resp = client.get("/api/admin/emails/threads?status=resolved,spam")
        assert resp.status_code == 200
        assert mock_list.call_args.args[0] == ["resolved", "spam"]

    def test_invalid_status_returns_400(self, admin_client):
        client, _ = admin_client
        resp = client.get("/api/admin/emails/threads?status=nope")
        assert resp.status_code == 400

    def test_cursor_passed_through_to_dao(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._threads_dao, "list_by_status",
            return_value={"items": [], "next_cursor": None},
        ) as mock_list:
            client.get("/api/admin/emails/threads?cursor=opaque-token")
        assert mock_list.call_args.kwargs["cursor"] == "opaque-token"

    def test_limit_clamped_by_query_validator(self, admin_client):
        client, _ = admin_client
        resp = client.get("/api/admin/emails/threads?limit=999")
        # 200 ≤ limit ≤ 200 enforced by FastAPI Query(le=200)
        assert resp.status_code == 422


class TestGetThreadEndpoint:
    def test_resolves_mt_n_form(self, admin_client):
        client, module = admin_client
        thread = {"id": "t1", "case_number": 42, "subject": "x", "status": "new"}
        with (
            patch.object(module._threads_dao, "get_by_case_number", return_value=thread),
            patch.object(module._threads_dao, "get_thread_with_messages",
                         return_value={**thread, "messages": []}),
        ):
            resp = client.get("/api/admin/emails/threads/MT-42")
        assert resp.status_code == 200
        assert resp.json()["case_number"] == 42

    def test_resolves_uuid_form(self, admin_client):
        client, module = admin_client
        thread = {"id": "abc-uuid", "case_number": 7, "subject": "x", "status": "new"}
        with (
            patch.object(module._threads_dao, "get_thread_by_id", return_value=thread),
            patch.object(module._threads_dao, "get_thread_with_messages",
                         return_value={**thread, "messages": [{"id": "m1"}]}),
        ):
            resp = client.get("/api/admin/emails/threads/abc-uuid")
        assert resp.status_code == 200
        assert resp.json()["messages"] == [{"id": "m1"}]

    def test_404_when_missing(self, admin_client):
        client, module = admin_client
        with patch.object(module._threads_dao, "get_by_case_number", return_value=None):
            resp = client.get("/api/admin/emails/threads/MT-9999")
        assert resp.status_code == 404


class TestPatchEndpoints:
    def test_patch_status_sets_status(self, admin_client):
        client, module = admin_client
        thread = {"id": "t1", "case_number": 1, "subject": "x", "status": "new"}
        with (
            patch.object(module._threads_dao, "get_thread_by_id", return_value=thread),
            patch.object(module._threads_dao, "set_status",
                         return_value={**thread, "status": "resolved"}) as set_status,
        ):
            resp = client.patch(
                "/api/admin/emails/threads/t1/status",
                json={"status": "resolved"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
        set_status.assert_called_once_with("t1", "resolved")

    def test_patch_status_rejects_invalid_status(self, admin_client):
        client, module = admin_client
        thread = {"id": "t1", "case_number": 1, "subject": "x", "status": "new"}
        with patch.object(module._threads_dao, "get_thread_by_id", return_value=thread):
            resp = client.patch(
                "/api/admin/emails/threads/t1/status",
                json={"status": "awaiting_user"},  # not a manual override
            )
        # Pydantic Literal rejects → 422.
        assert resp.status_code == 422

    def test_patch_read_zeros_unread(self, admin_client):
        client, module = admin_client
        thread = {"id": "t1", "case_number": 1, "subject": "x", "status": "new"}
        with (
            patch.object(module._threads_dao, "get_thread_by_id", return_value=thread),
            patch.object(module._threads_dao, "mark_all_read", return_value=3) as mark,
        ):
            resp = client.patch("/api/admin/emails/threads/t1/read")
        assert resp.status_code == 200
        assert resp.json() == {"thread_id": "t1", "messages_marked_read": 3}
        mark.assert_called_once_with("t1")


class TestUnreadCountEndpoint:
    def test_returns_summed_count(self, admin_client):
        client, module = admin_client
        with patch.object(
            module._threads_dao, "unread_count_for_attention", return_value=7
        ):
            resp = client.get("/api/admin/emails/unread-count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 7}


class TestReplyEndpoint:
    def test_reply_orchestrator_called_with_thread_and_admin_id(self, admin_client):
        client, module = admin_client
        thread = {
            "id": "t1", "case_number": 1, "subject": "My Q",
            "participant_email": "j@x", "status": "awaiting_admin",
        }
        inserted = {"id": "msg-row", "direction": "outbound", "thread_id": "t1"}

        with (
            patch.object(module._threads_dao, "get_thread_by_id", return_value=thread),
            patch("api.admin_emails.send_admin_reply", return_value=inserted) as send,
        ):
            resp = client.post(
                "/api/admin/emails/threads/t1/reply",
                json={"body_text": "Thanks for reaching out!"},
            )

        assert resp.status_code == 200
        assert resp.json() == inserted
        kwargs = send.call_args.kwargs
        assert kwargs["thread"] is thread
        assert kwargs["body_text"] == "Thanks for reaching out!"
        assert kwargs["admin_user_id"] == "admin-user-1"

    def test_reply_rejects_empty_body(self, admin_client):
        client, _ = admin_client
        resp = client.post(
            "/api/admin/emails/threads/t1/reply",
            json={"body_text": ""},
        )
        assert resp.status_code == 422  # min_length=1

    def test_reply_502_when_send_fails(self, admin_client):
        client, module = admin_client
        thread = {
            "id": "t1", "case_number": 1, "subject": "My Q",
            "participant_email": "j@x", "status": "awaiting_admin",
        }
        with (
            patch.object(module._threads_dao, "get_thread_by_id", return_value=thread),
            patch(
                "api.admin_emails.send_admin_reply",
                side_effect=RuntimeError("resend exploded"),
            ),
        ):
            resp = client.post(
                "/api/admin/emails/threads/t1/reply",
                json={"body_text": "hi"},
            )
        assert resp.status_code == 502


class TestAuthGating:
    def test_requires_admin(self):
        """Without the dependency override, require_admin on a 403-rolled user."""
        from api import admin_emails
        from auth import require_admin

        app = FastAPI()
        app.include_router(admin_emails.router)
        # Simulate an authenticated non-admin user. require_admin checks role.
        def _non_admin():
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")
        app.dependency_overrides[require_admin] = _non_admin

        client = TestClient(app)
        for path in [
            "/api/admin/emails/threads",
            "/api/admin/emails/unread-count",
            "/api/admin/emails/threads/MT-1",
        ]:
            resp = client.get(path)
            assert resp.status_code == 403, path
