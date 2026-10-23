"""Reviewing an invite request (SB-1392).

Approve and Create invite were one decision split across two buttons: the
status endpoint could approve a request without creating its invitation.
Now a request is approved only by creating the invitation (see
test_invite_request_link.py); the status endpoint rejects or resets, and a
rejection emails the requester. A linked invitation's email can be resent.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit, pytest.mark.backend]

REQUEST_ID = "11111111-1111-1111-1111-111111111111"
ADMIN = {"id": "admin-1", "user_id": "admin-1", "role": "admin"}

PENDING = {
    "id": REQUEST_ID,
    "email": "pat@example.com",
    "name": "Pat Fan",
    "status": "pending",
    "invitation_id": None,
}


def _requests_db(row):
    """service_client for invite_requests: the lookup returns `row`, the
    update echoes it back with the new fields."""
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[row] if row else [])

    def update(data):
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = SimpleNamespace(data=[{**(row or {}), **data}])
        return chain

    table.update.side_effect = update
    return client


@pytest.fixture
def review(monkeypatch):
    from api import invite_requests
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(invite_requests.router)
    app.dependency_overrides[get_current_user_required] = lambda: ADMIN

    def with_row(row):
        db = _requests_db(row)
        monkeypatch.setattr(invite_requests, "service_client", db)
        return db

    with_row(PENDING)
    return SimpleNamespace(client=TestClient(app), with_row=with_row)


def _put(review, status):
    return review.client.put(f"/api/invite-requests/{REQUEST_ID}/status", json={"status": status})


class TestStatusEndpoint:
    def test_approved_is_not_a_status_you_can_set(self, review):
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, "approved")

        assert resp.status_code == 422
        email.assert_not_called()

    def test_reject_sets_rejected_and_emails_the_requester(self, review):
        with patch("api.invite_requests.EmailService") as email:
            email.return_value.send_invite_request_rejection.return_value = True
            resp = _put(review, "rejected")

        assert resp.status_code == 200
        body = resp.json()
        assert body["request"]["status"] == "rejected"
        assert body["request"]["reviewed_by"] == "admin-1"
        assert body["email_sent"] is True
        email.return_value.send_invite_request_rejection.assert_called_once_with(
            to_email="pat@example.com", name="Pat Fan"
        )

    def test_rejecting_again_does_not_email_again(self, review):
        review.with_row({**PENDING, "status": "rejected"})
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, "rejected")

        assert resp.status_code == 200
        assert resp.json()["email_sent"] is False
        email.assert_not_called()

    def test_a_failed_rejection_email_still_rejects(self, review):
        with patch("api.invite_requests.EmailService", side_effect=RuntimeError("no RESEND_API_KEY")):
            resp = _put(review, "rejected")

        assert resp.status_code == 200
        assert resp.json()["request"]["status"] == "rejected"
        assert resp.json()["email_sent"] is False

    def test_reset_sends_nothing(self, review):
        review.with_row({**PENDING, "status": "rejected"})
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, "pending")

        assert resp.status_code == 200
        assert resp.json()["request"]["status"] == "pending"
        email.assert_not_called()

    def test_existing_user_closes_the_request_without_an_email(self, review):
        """SB-1408: a requester who already has an account is neither
        rejected (that emails them) nor invited again."""
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, "existing_user")

        assert resp.status_code == 200
        body = resp.json()
        assert body["request"]["status"] == "existing_user"
        assert body["request"]["reviewed_by"] == "admin-1"
        assert body["email_sent"] is False
        email.assert_not_called()

    def test_existing_user_can_be_reset(self, review):
        review.with_row({**PENDING, "status": "existing_user"})
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, "pending")

        assert resp.status_code == 200
        assert resp.json()["request"]["status"] == "pending"
        email.assert_not_called()

    def test_legacy_approval_without_an_invitation_can_be_reset(self, review):
        review.with_row({**PENDING, "status": "approved"})
        with patch("api.invite_requests.EmailService"):
            resp = _put(review, "pending")

        assert resp.status_code == 200

    @pytest.mark.parametrize("status", ["pending", "rejected", "existing_user"])
    def test_a_linked_request_cannot_change(self, review, status):
        db = review.with_row({**PENDING, "status": "approved", "invitation_id": "inv-1"})
        with patch("api.invite_requests.EmailService") as email:
            resp = _put(review, status)

        assert resp.status_code == 409
        db.table.return_value.update.assert_not_called()
        email.assert_not_called()

    def test_test_approval_email_endpoint_is_gone(self, review):
        resp = review.client.post("/api/invite-requests/test-approval-email", json={"to_email": "pat@example.com"})
        assert resp.status_code in (404, 405)


class TestRejectionEmail:
    def test_escapes_the_requesters_name_in_html(self, monkeypatch):
        from services import email_service

        monkeypatch.setenv("RESEND_API_KEY", "re_test")
        sent = {}
        monkeypatch.setattr(email_service.resend.Emails, "send", lambda payload: sent.update(payload))

        ok = email_service.EmailService().send_invite_request_rejection("pat@example.com", "<b>Pat</b>")

        assert ok is True
        assert "&lt;b&gt;Pat&lt;/b&gt;" in sent["html"]
        assert "<b>Pat</b>" not in sent["html"]
        assert "Hi <b>Pat</b>," in sent["text"]

    def test_provider_failure_returns_false(self, monkeypatch):
        from services import email_service

        monkeypatch.setenv("RESEND_API_KEY", "re_test")

        def boom(_payload):
            raise RuntimeError("refused")

        monkeypatch.setattr(email_service.resend.Emails, "send", boom)

        assert email_service.EmailService().send_invite_request_rejection("pat@example.com", "Pat") is False


class TestTestRejectionEmailEndpoint:
    """Preview the rejection template before a real Reject (SB-1407)."""

    def _post(self, review, **body):
        return review.client.post(
            "/api/invite-requests/test-rejection-email", json={"to_email": "me@example.com", **body}
        )

    def test_sends_the_rejection_template_and_touches_no_row(self, review):
        db = review.with_row(PENDING)
        with patch("api.invite_requests.EmailService") as svc:
            svc.return_value.send_invite_request_rejection.return_value = True
            response = self._post(review, name="Me")

        assert response.status_code == 200
        svc.return_value.send_invite_request_rejection.assert_called_once_with(to_email="me@example.com", name="Me")
        db.table.assert_not_called()

    def test_send_failure_is_502(self, review):
        with patch("api.invite_requests.EmailService") as svc:
            svc.return_value.send_invite_request_rejection.return_value = False
            response = self._post(review)

        assert response.status_code == 502

    def test_unconfigured_email_is_503_without_details(self, review):
        with patch("api.invite_requests.EmailService", side_effect=RuntimeError("RESEND_API_KEY missing")):
            response = self._post(review)

        assert response.status_code == 503
        assert "RESEND_API_KEY" not in response.text

    def test_non_admin_is_403(self, review):
        from auth import get_current_user_required

        review.client.app.dependency_overrides[get_current_user_required] = lambda: {"id": "u", "role": "team-fan"}
        with patch("api.invite_requests.EmailService") as svc:
            response = self._post(review)

        assert response.status_code == 403
        svc.assert_not_called()


INVITATION = {
    "id": "inv-1",
    "email": "pat@example.com",
    "invite_code": "ABCDEFGHJKLM",
    "invite_type": "club_fan",
    "expires_at": "2026-10-30T00:00:00+00:00",
    "status": "pending",
    "testflight_status": "added",
    "testflight_email": "pat.apple@example.com",
}


def _invite_service(row):
    from services.invite_service import InviteService

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[row] if row else []
    )
    return InviteService(client)


class TestResendInviteEmail:
    def test_resends_with_the_invitations_own_details(self):
        with patch("services.email_service.EmailService") as email:
            email.return_value.send_invitation.return_value = True
            assert _invite_service(INVITATION).resend_email("inv-1") is True

        email.return_value.send_invitation.assert_called_once_with(
            to_email="pat@example.com",
            invite_code="ABCDEFGHJKLM",
            invite_type="club_fan",
            expires_at="2026-10-30T00:00:00+00:00",
            ios_beta=True,
            testflight_email="pat.apple@example.com",
        )

    def test_no_testflight_means_no_beta_steps(self):
        row = {**INVITATION, "testflight_status": None, "testflight_email": None}
        with patch("services.email_service.EmailService") as email:
            _invite_service(row).resend_email("inv-1")

        assert email.return_value.send_invitation.call_args.kwargs["ios_beta"] is False

    def test_missing_invitation(self):
        with pytest.raises(LookupError):
            _invite_service(None).resend_email("inv-1")

    @pytest.mark.parametrize("row", [{**INVITATION, "email": None}, {**INVITATION, "status": "used"}])
    def test_refuses_without_email_or_once_used(self, row):
        with patch("services.email_service.EmailService") as email, pytest.raises(ValueError):
            _invite_service(row).resend_email("inv-1")
        email.assert_not_called()


@pytest.fixture
def invites_api(monkeypatch):
    from api import invites
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(invites.router)
    user = {"value": ADMIN}
    app.dependency_overrides[get_current_user_required] = lambda: user["value"]
    service = MagicMock()
    monkeypatch.setattr(invites, "InviteService", lambda _client: service)
    monkeypatch.setattr(invites, "service_client", MagicMock())
    return SimpleNamespace(client=TestClient(app), service=service, user=user)


class TestResendEndpoint:
    URL = "/api/invites/admin/inv-1/resend-email"

    def test_admin_resends(self, invites_api):
        invites_api.service.resend_email.return_value = True
        resp = invites_api.client.post(self.URL)

        assert resp.status_code == 200
        invites_api.service.resend_email.assert_called_once_with("inv-1")

    def test_provider_refusal_is_502(self, invites_api):
        invites_api.service.resend_email.return_value = False
        assert invites_api.client.post(self.URL).status_code == 502

    @pytest.mark.parametrize(("error", "code"), [(LookupError("x"), 404), (ValueError("x"), 400)])
    def test_errors_map_to_status(self, invites_api, error, code):
        invites_api.service.resend_email.side_effect = error
        assert invites_api.client.post(self.URL).status_code == code

    @pytest.mark.parametrize("role", ["club_manager", "team_manager", "user"])
    def test_admin_only(self, invites_api, role):
        invites_api.user["value"] = {**ADMIN, "role": role}
        assert invites_api.client.post(self.URL).status_code == 403
        invites_api.service.resend_email.assert_not_called()
