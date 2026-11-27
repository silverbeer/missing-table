"""Email delivery status from Resend webhooks (SB-1814, SB-1821 for replies).

Covers:
- the send path: the Resend id is captured and stored with status 'sent';
  a resend replaces it
- services/email_delivery: event mapping, precedence, retries, unknown ids
- POST /api/webhooks/email/inbound routes delivery events there, and leaves
  email.received and signature handling alone
- support replies: an id no invitation carries falls through to outbound
  email_messages (SB-1821)

No database: a small in-memory stand-in for the invitations table, so a
sequence of events is applied to one row the way it would be in prod.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit, pytest.mark.backend]

EMAIL_ID = "4ef9a417-02e9-4d39-ad75-9611e0fcc33c"


class _Query:
    """Just enough of the supabase query builder for email_delivery."""

    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters: list = []
        self._update: dict | None = None

    def select(self, _cols):
        return self

    def update(self, data):
        self._update = data
        return self

    def eq(self, col, value):
        self._filters.append(lambda r: r.get(col) == value)
        return self

    def is_(self, col, value):
        assert value == "null"
        self._filters.append(lambda r: r.get(col) is None)
        return self

    def limit(self, _n):
        return self

    def execute(self):
        matched = [r for r in self._rows if all(f(r) for f in self._filters)]
        if self._update is not None:
            for r in matched:
                r.update(self._update)
        return SimpleNamespace(data=[dict(r) for r in matched])


class _FakeDb:
    """`rows` are invitations; `messages` are email_messages (SB-1821)."""

    def __init__(self, *rows: dict, messages: tuple[dict, ...] = ()):
        self.rows = [dict(r) for r in rows]
        self.messages = [dict(m) for m in messages]

    def table(self, name):
        assert name in ("invitations", "email_messages")
        return _Query(self.rows if name == "invitations" else self.messages)


def _row(**overrides) -> dict:
    return {"id": "inv-1", "resend_email_id": EMAIL_ID, "email_status": "sent", **overrides}


def _event(event_type: str, created_at: str = "2026-11-27T12:00:00.000Z", **data) -> dict:
    return {
        "type": event_type,
        "created_at": created_at,
        "data": {
            "email_id": EMAIL_ID,
            "to": ["pat@example.com"],
            "subject": "You're invited to Missing Table",
            "created_at": "2026-11-27T11:59:00.000Z",
            **data,
        },
    }


# ── pure helpers ─────────────────────────────────────────────────────────────


class TestMapping:
    @pytest.mark.parametrize(
        ("event_type", "status"),
        [
            ("email.sent", "sent"),
            ("email.delivered", "delivered"),
            ("email.delivery_delayed", "delayed"),
            ("email.bounced", "bounced"),
            ("email.complained", "complained"),
            ("email.failed", "failed"),
            ("email.suppressed", "suppressed"),
        ],
    )
    def test_delivery_events_map_to_a_status(self, event_type, status):
        from services.email_delivery import status_for_event

        assert status_for_event(event_type) == status

    @pytest.mark.parametrize(
        "event_type", ["email.opened", "email.clicked", "email.scheduled", "email.received", None, "x"]
    )
    def test_other_events_map_to_nothing(self, event_type):
        from services.email_delivery import status_for_event

        assert status_for_event(event_type) is None

    def test_bounce_detail_is_generic(self):
        from services.email_delivery import bounce_detail

        data = {
            "bounce": {
                "type": "Permanent",
                "subType": "Suppressed",
                "message": "550 5.1.1 <pat@example.com>: user unknown at mx.example.com",
            }
        }
        assert bounce_detail(data) == "Permanent: Suppressed"

    def test_bounce_detail_absent(self):
        from services.email_delivery import bounce_detail

        assert bounce_detail({}) is None
        assert bounce_detail({"bounce": {}}) is None


# ── record_delivery_event ────────────────────────────────────────────────────


class TestRecordDeliveryEvent:
    @pytest.mark.parametrize(
        ("event_type", "status"),
        [
            ("email.delivered", "delivered"),
            ("email.delivery_delayed", "delayed"),
            ("email.bounced", "bounced"),
            ("email.complained", "complained"),
            ("email.failed", "failed"),
            ("email.suppressed", "suppressed"),
        ],
    )
    def test_each_event_is_recorded(self, event_type, status):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        result = record_delivery_event(db, _event(event_type))

        assert result == {"status": "recorded", "email_status": status}
        assert db.rows[0]["email_status"] == status
        assert db.rows[0]["email_status_at"] == "2026-11-27T12:00:00.000Z"

    def test_sent_fills_in_an_untracked_row(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row(email_status=None))
        record_delivery_event(db, _event("email.sent"))
        assert db.rows[0]["email_status"] == "sent"

    def test_bounce_stores_the_generic_reason_only(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        record_delivery_event(
            db,
            _event(
                "email.bounced",
                bounce={"type": "Permanent", "subType": "General", "message": "550 raw smtp for pat@example.com"},
            ),
        )
        assert db.rows[0]["email_status_detail"] == "Permanent: General"
        assert "pat@" not in json.dumps(db.rows[0])

    def test_unknown_email_id_is_ignored(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row(resend_email_id="some-support-reply"))
        result = record_delivery_event(db, _event("email.delivered"))

        assert result["status"] == "ignored"
        assert db.rows[0]["email_status"] == "sent"

    @pytest.mark.parametrize("event_type", ["email.opened", "email.clicked", "email.scheduled"])
    def test_engagement_events_are_ignored(self, event_type):
        from services.email_delivery import record_delivery_event

        db = MagicMock()
        assert record_delivery_event(db, _event(event_type))["status"] == "ignored"
        db.table.assert_not_called()

    def test_missing_email_id_is_ignored_without_a_lookup(self):
        from services.email_delivery import record_delivery_event

        db = MagicMock()
        assert record_delivery_event(db, {"type": "email.delivered", "data": {}})["status"] == "ignored"
        db.table.assert_not_called()

    def test_delivered_then_bounced_is_bounced(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        record_delivery_event(db, _event("email.delivered"))
        record_delivery_event(db, _event("email.bounced", bounce={"type": "Permanent", "subType": "General"}))
        assert db.rows[0]["email_status"] == "bounced"

    def test_bounced_then_delivered_stays_bounced(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        record_delivery_event(
            db, _event("email.bounced", "2026-11-27T12:00:00Z", bounce={"type": "Permanent", "subType": "General"})
        )
        result = record_delivery_event(db, _event("email.delivered", "2026-11-27T12:05:00Z"))

        assert result == {"status": "unchanged", "email_status": "bounced"}
        assert db.rows[0]["email_status"] == "bounced"
        assert db.rows[0]["email_status_at"] == "2026-11-27T12:00:00Z"
        assert db.rows[0]["email_status_detail"] == "Permanent: General"

    def test_delivered_then_complained_is_complained(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        record_delivery_event(db, _event("email.delivered"))
        record_delivery_event(db, _event("email.complained"))
        assert db.rows[0]["email_status"] == "complained"

    def test_late_sent_or_delayed_never_downgrades(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        record_delivery_event(db, _event("email.delivered"))
        record_delivery_event(db, _event("email.delivery_delayed"))
        record_delivery_event(db, _event("email.sent"))
        assert db.rows[0]["email_status"] == "delivered"

    def test_a_retry_is_idempotent(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row())
        event = _event("email.delivered")
        first = record_delivery_event(db, event)
        snapshot = dict(db.rows[0])
        second = record_delivery_event(db, event)

        assert first["status"] == "recorded"
        assert second == {"status": "unchanged", "email_status": "delivered"}
        assert db.rows[0] == snapshot

    def test_write_is_compare_and_set(self):
        """A concurrent writer that changed the status first wins: the update
        only matches the status that was read."""
        from services.email_delivery import record_delivery_event

        db = MagicMock()
        select = db.table.return_value.select.return_value.eq.return_value.limit.return_value
        select.execute.return_value = SimpleNamespace(data=[{"id": "inv-1", "email_status": "sent"}])
        record_delivery_event(db, _event("email.delivered"))

        update_chain = db.table.return_value.update.return_value
        update_chain.eq.assert_called_once_with("id", "inv-1")
        update_chain.eq.return_value.eq.assert_called_once_with("resend_email_id", EMAIL_ID)
        update_chain.eq.return_value.eq.return_value.eq.assert_called_once_with("email_status", "sent")

    def test_logs_never_carry_the_full_address(self):
        from services import email_delivery

        db = _FakeDb(_row())
        with patch.object(email_delivery, "logger") as log:
            email_delivery.record_delivery_event(db, _event("email.delivered"))
        logged = json.dumps([c.kwargs for c in log.info.call_args_list])
        assert "pat@example.com" not in logged
        assert "pat***@example.com" in logged


# ── webhook routing ──────────────────────────────────────────────────────────


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_test")
    from api import webhooks_email

    app = FastAPI()
    app.include_router(webhooks_email.router)
    db = _FakeDb(_row())
    monkeypatch.setattr(webhooks_email._db_conn, "client", db, raising=False)
    return TestClient(app), db


def _post(client, event):
    return client.post(
        "/api/webhooks/email/inbound",
        content=json.dumps(event).encode(),
        headers={"content-type": "application/json"},
    )


class TestWebhookRouting:
    def test_delivery_event_is_recorded(self, webhook):
        client, db = webhook
        with patch("api.webhooks_email.verify_webhook"):
            resp = _post(client, _event("email.delivered"))

        assert resp.status_code == 200
        assert resp.json() == {"status": "recorded", "email_status": "delivered"}
        assert db.rows[0]["email_status"] == "delivered"

    def test_unknown_email_id_is_200_ignored(self, webhook):
        client, db = webhook
        event = _event("email.bounced")
        event["data"]["email_id"] = "not-an-invite"
        with patch("api.webhooks_email.verify_webhook"):
            resp = _post(client, event)

        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert db.rows[0]["email_status"] == "sent"

    def test_bad_signature_is_still_401(self, webhook):
        from services.email_inbound import WebhookVerificationError

        client, db = webhook
        with patch("api.webhooks_email.verify_webhook", side_effect=WebhookVerificationError("bad sig")):
            resp = _post(client, _event("email.delivered"))

        assert resp.status_code == 401
        assert db.rows[0]["email_status"] == "sent"

    def test_received_still_goes_to_the_inbound_path(self, webhook):
        client, db = webhook
        with (
            patch("api.webhooks_email.verify_webhook"),
            patch("api.webhooks_email.record_delivery_event") as delivery,
            patch("api.webhooks_email._fetch_received_email", return_value={}) as fetch,
        ):
            resp = _post(client, {"type": "email.received", "data": {"email_id": "in-1"}})

        delivery.assert_not_called()
        fetch.assert_called_once_with("in-1")
        # No message_id on the fetched email: the existing inbound 400.
        assert resp.status_code == 400

    def test_opened_is_ignored(self, webhook):
        client, _ = webhook
        with patch("api.webhooks_email.verify_webhook"):
            resp = _post(client, _event("email.opened"))
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── send path ────────────────────────────────────────────────────────────────


class TestSendCapturesId:
    def test_send_invitation_keeps_returning_bool_and_exposes_the_id(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        from services.email_service import EmailService

        service = EmailService()
        with patch("resend.Emails.send", return_value={"id": EMAIL_ID}):
            assert service.send_invitation("a@example.com", "ABCDEFGHJKLM", "club_fan") is True
        assert service.last_email_id == EMAIL_ID

    def test_a_failed_send_clears_the_id(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        from services.email_service import EmailService

        service = EmailService()
        service.last_email_id = "stale"
        with patch("resend.Emails.send", side_effect=Exception("nope")):
            assert service.send_invitation("a@example.com", "ABCDEFGHJKLM") is False
        assert service.last_email_id is None


def _invite_client(row: dict):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[row])
    client.table.return_value.insert.return_value.execute.return_value.data = [dict(row)]
    return client


def _updates(client) -> list[dict]:
    return [c.args[0] for c in client.table.return_value.update.call_args_list]


class TestInviteServiceStoresId:
    def _email(self, email_id=EMAIL_ID, sent=True):
        email = MagicMock()
        email.return_value.send_invitation.return_value = sent
        email.return_value.last_email_id = email_id
        return email

    def test_create_stores_the_id_as_sent(self):
        from services.invite_service import InviteService

        client = _invite_client({"id": "inv-1", "invite_code": "ABCDEFGHJKLM"})
        # Invite codes are unique: the uniqueness probe finds nothing.
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])
        with patch("services.email_service.EmailService", self._email()):
            result = InviteService(client).create_invitation(
                invited_by_user_id="admin-1", invite_type="club_fan", club_id=10, email="a@example.com"
            )

        (update,) = _updates(client)
        assert update["resend_email_id"] == EMAIL_ID
        assert update["email_status"] == "sent"
        assert update["email_status_at"]
        assert result["email_status"] == "sent"

    def test_create_without_an_id_records_nothing(self):
        from services.invite_service import InviteService

        client = _invite_client({"id": "inv-1"})
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])
        with patch("services.email_service.EmailService", self._email(email_id=None)):
            result = InviteService(client).create_invitation(
                invited_by_user_id="admin-1", invite_type="club_fan", club_id=10, email="a@example.com"
            )
        assert _updates(client) == []
        assert "email_status" not in result

    def test_failing_to_record_does_not_fail_the_invite(self):
        from services.invite_service import InviteService

        client = _invite_client({"id": "inv-1"})
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])
        client.table.return_value.update.side_effect = Exception("column does not exist")
        with patch("services.email_service.EmailService", self._email()):
            result = InviteService(client).create_invitation(
                invited_by_user_id="admin-1", invite_type="club_fan", club_id=10, email="a@example.com"
            )
        assert result["id"] == "inv-1"

    def test_resend_replaces_the_id_and_resets_to_sent(self):
        from services.invite_service import InviteService

        row = {
            "id": "inv-1",
            "email": "pat@example.com",
            "invite_code": "ABCDEFGHJKLM",
            "status": "pending",
            "resend_email_id": "old-id",
            "email_status": "bounced",
            "email_status_detail": "Permanent: General",
        }
        client = _invite_client(row)
        with patch("services.email_service.EmailService", self._email(email_id="new-id")):
            assert InviteService(client).resend_email("inv-1") is True

        (update,) = _updates(client)
        assert update["resend_email_id"] == "new-id"
        assert update["email_status"] == "sent"
        assert update["email_status_detail"] is None

    def test_a_refused_resend_keeps_the_old_status(self):
        from services.invite_service import InviteService

        row = {"id": "inv-1", "email": "pat@example.com", "invite_code": "X", "status": "pending"}
        client = _invite_client(row)
        with patch("services.email_service.EmailService", self._email(sent=False)):
            assert InviteService(client).resend_email("inv-1") is False
        assert _updates(client) == []


# ── support replies (SB-1821) ────────────────────────────────────────────────


def _reply(**overrides) -> dict:
    return {"id": "msg-1", "direction": "outbound", "resend_email_id": EMAIL_ID, "email_status": "sent", **overrides}


class TestReplyDelivery:
    def test_event_for_a_reply_is_recorded(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(messages=(_reply(),))
        result = record_delivery_event(db, _event("email.delivered"))

        assert result == {"status": "recorded", "email_status": "delivered"}
        assert db.messages[0]["email_status"] == "delivered"
        assert db.messages[0]["email_status_at"] == "2026-11-27T12:00:00.000Z"

    def test_reply_bounce_stores_the_generic_reason_only(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(messages=(_reply(),))
        record_delivery_event(
            db, _event("email.bounced", bounce={"type": "Permanent", "subType": "General", "message": "550 pat@x"})
        )
        assert db.messages[0]["email_status"] == "bounced"
        assert db.messages[0]["email_status_detail"] == "Permanent: General"

    def test_reply_precedence(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(messages=(_reply(),))
        record_delivery_event(db, _event("email.bounced", bounce={"type": "Permanent", "subType": "General"}))
        result = record_delivery_event(db, _event("email.delivered"))
        record_delivery_event(db, _event("email.sent"))

        assert result == {"status": "unchanged", "email_status": "bounced"}
        assert db.messages[0]["email_status"] == "bounced"

    def test_reply_retry_is_idempotent(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(messages=(_reply(),))
        record_delivery_event(db, _event("email.delivered"))
        snapshot = dict(db.messages[0])
        assert record_delivery_event(db, _event("email.delivered"))["status"] == "unchanged"
        assert db.messages[0] == snapshot

    def test_inbound_rows_are_never_matched(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(messages=(_reply(direction="inbound"),))
        assert record_delivery_event(db, _event("email.delivered"))["status"] == "ignored"
        assert db.messages[0]["email_status"] == "sent"

    def test_invitation_is_preferred_and_the_reply_untouched(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row(), messages=(_reply(),))
        record_delivery_event(db, _event("email.delivered"))

        assert db.rows[0]["email_status"] == "delivered"
        assert db.messages[0]["email_status"] == "sent"

    def test_neither_matches_is_ignored(self):
        from services.email_delivery import record_delivery_event

        db = _FakeDb(_row(resend_email_id="other"), messages=(_reply(resend_email_id="another"),))
        assert record_delivery_event(db, _event("email.delivered"))["status"] == "ignored"
        assert db.rows[0]["email_status"] == "sent"
        assert db.messages[0]["email_status"] == "sent"

    def test_reply_write_is_compare_and_set_on_outbound(self):
        from services.email_delivery import record_delivery_event

        db = MagicMock()
        invitations, messages = MagicMock(), MagicMock()
        db.table.side_effect = lambda name: invitations if name == "invitations" else messages
        invitations.select.return_value.eq.return_value.limit.return_value.execute.return_value = SimpleNamespace(
            data=[]
        )
        messages.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = (
            SimpleNamespace(data=[{"id": "msg-1", "email_status": "sent"}])
        )
        record_delivery_event(db, _event("email.delivered"))

        messages.select.return_value.eq.assert_called_once_with("resend_email_id", EMAIL_ID)
        messages.select.return_value.eq.return_value.eq.assert_called_once_with("direction", "outbound")
        chain = messages.update.return_value
        chain.eq.assert_called_once_with("id", "msg-1")
        chain.eq.return_value.eq.assert_called_once_with("resend_email_id", EMAIL_ID)
        chain.eq.return_value.eq.return_value.eq.assert_called_once_with("email_status", "sent")
        chain.eq.return_value.eq.return_value.eq.return_value.eq.assert_called_once_with("direction", "outbound")

    def test_reply_logs_mask_the_recipient(self):
        from services import email_delivery

        db = _FakeDb(messages=(_reply(),))
        with patch.object(email_delivery, "logger") as log:
            email_delivery.record_delivery_event(db, _event("email.delivered"))
        logged = json.dumps([c.kwargs for c in log.info.call_args_list])
        assert "pat@example.com" not in logged
        assert "pat***@example.com" in logged

    def test_webhook_records_a_reply(self, monkeypatch):
        monkeypatch.setenv("EMAIL_INBOUND_WEBHOOK_SECRET", "whsec_test")
        from api import webhooks_email

        app = FastAPI()
        app.include_router(webhooks_email.router)
        db = _FakeDb(messages=(_reply(),))
        monkeypatch.setattr(webhooks_email._db_conn, "client", db, raising=False)
        with patch("api.webhooks_email.verify_webhook"):
            resp = _post(TestClient(app), _event("email.delivered"))

        assert resp.status_code == 200
        assert resp.json() == {"status": "recorded", "email_status": "delivered"}
        assert db.messages[0]["email_status"] == "delivered"


class TestReplySendStoresId:
    def _daos(self):
        threads, messages = MagicMock(), MagicMock()
        messages.get_latest_inbound_for_thread.return_value = None
        messages.insert_outbound.return_value = {"id": "msg-1", "direction": "outbound"}
        messages.record_reply_sent.side_effect = lambda row_id, email_id, sent_at: {
            "resend_email_id": email_id,
            "email_status": "sent",
            "email_status_at": sent_at,
            "email_status_detail": None,
        }
        return threads, messages

    def _send(self, monkeypatch, threads, messages, **send_kwargs):
        from services import email_outbound

        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        thread = {"id": "t-1", "case_number": 7, "subject": "Q", "participant_email": "pat@example.com"}
        with patch.object(email_outbound.resend.Emails, "send", **send_kwargs):
            return email_outbound.send_admin_reply(
                threads, messages, thread=thread, body_text="hi", body_html=None, admin_user_id="admin-1"
            )

    def test_stores_the_id_as_sent(self, monkeypatch):
        threads, messages = self._daos()
        row = self._send(monkeypatch, threads, messages, return_value={"id": EMAIL_ID})

        args = messages.record_reply_sent.call_args.args
        assert args[:2] == ("msg-1", EMAIL_ID)
        assert args[2]
        assert row["resend_email_id"] == EMAIL_ID
        assert row["email_status"] == "sent"

    def test_insert_carries_no_delivery_columns(self, monkeypatch):
        """The reply row is inserted exactly as before SB-1821, so an
        unmigrated database still saves it."""
        threads, messages = self._daos()
        self._send(monkeypatch, threads, messages, return_value={"id": EMAIL_ID})
        ins = messages.insert_outbound.call_args.kwargs
        assert not {"resend_email_id", "email_status"} & ins.keys()

    def test_failing_to_record_does_not_fail_the_reply(self, monkeypatch):
        threads, messages = self._daos()
        messages.record_reply_sent.side_effect = Exception("column does not exist")
        row = self._send(monkeypatch, threads, messages, return_value={"id": EMAIL_ID})

        assert row == {"id": "msg-1", "direction": "outbound"}
        threads.transition_on_outbound.assert_called_once()

    def test_no_id_records_nothing(self, monkeypatch):
        threads, messages = self._daos()
        row = self._send(monkeypatch, threads, messages, return_value={})
        messages.record_reply_sent.assert_not_called()
        assert "email_status" not in row

    def test_dao_updates_only_the_outbound_row(self):
        from dao.email_messages_dao import EmailMessagesDAO

        dao = EmailMessagesDAO.__new__(EmailMessagesDAO)
        dao.client = MagicMock()
        # The undecorated method: cache invalidation is BaseDAO's concern.
        update = EmailMessagesDAO.record_reply_sent.__wrapped__(dao, "msg-1", EMAIL_ID, "2026-11-27T12:00:00Z")

        assert update["email_status"] == "sent"
        chain = dao.client.table.return_value.update
        chain.assert_called_once_with(update)
        chain.return_value.eq.assert_called_once_with("id", "msg-1")
        chain.return_value.eq.return_value.eq.assert_called_once_with("direction", "outbound")
