"""Creating an invitation from an invite request (SB-1312).

An admin invite endpoint given invite_request_id checks the request first,
creates the invite, then marks the request approved and links it. The old
"you're approved" email is not sent on this path.
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
CLUB_MANAGER = {"id": "cm-1", "user_id": "cm-1", "role": "club_manager", "club_id": 10}
TEAM_MANAGER = {"id": "tm-1", "user_id": "tm-1", "role": "team_manager"}

CLUB_BODY = {"club_id": 10, "email": "pat@example.com", "invite_request_id": REQUEST_ID}
TEAM_BODY = {
    "invite_type": "team_player",
    "team_id": 5,
    "age_group_id": 3,
    "email": "pat@example.com",
    "invite_request_id": REQUEST_ID,
}

ADMIN_PATHS = [
    ("/api/invites/admin/club-manager", CLUB_BODY),
    ("/api/invites/admin/club-fan", CLUB_BODY),
    ("/api/invites/admin/team-manager", dict(TEAM_BODY, invite_type="team_manager")),
    ("/api/invites/admin/team-player", TEAM_BODY),
    ("/api/invites/admin/team-fan", dict(TEAM_BODY, invite_type="team_fan")),
]


def _db(request_row=None, linked=True):
    """service_client: the request lookup returns `request_row`; the link update
    returns a row unless `linked` is False."""
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[request_row] if request_row else []
    )
    table.update.return_value.eq.return_value.eq.return_value.is_.return_value.execute.return_value = SimpleNamespace(
        data=[{"id": REQUEST_ID}] if linked else []
    )
    return client


PENDING = {"id": REQUEST_ID, "status": "pending", "invitation_id": None}


@pytest.fixture
def api(monkeypatch):
    from api import invites
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(invites.router)
    user = {"value": ADMIN}
    app.dependency_overrides[get_current_user_required] = lambda: user["value"]

    service = MagicMock()
    service.create_invitation.return_value = {"id": "inv-1", "invite_code": "ABCDEFGHJKLM"}
    monkeypatch.setattr(invites, "InviteService", lambda _client: service)
    manager_service = MagicMock()
    manager_service.can_manage_team.return_value = True
    monkeypatch.setattr(invites, "TeamManagerService", lambda _client: manager_service)

    state = {"db": _db(PENDING)}
    monkeypatch.setattr(invites, "service_client", state["db"])

    def as_user(u):
        user["value"] = u

    def with_db(db):
        state["db"] = db
        monkeypatch.setattr(invites, "service_client", db)
        return db

    return SimpleNamespace(client=TestClient(app), service=service, as_user=as_user, with_db=with_db, state=state)


def _update_payload(db) -> dict:
    return db.table.return_value.update.call_args.args[0]


class TestLinking:
    @pytest.mark.parametrize(("path", "body"), ADMIN_PATHS)
    def test_admin_invite_links_and_approves_the_request(self, api, path, body):
        db = api.state["db"]
        with patch("api.invite_requests.EmailService") as approval_email:
            resp = api.client.post(path, json=body)

        assert resp.status_code == 200
        assert resp.json()["id"] == "inv-1"
        api.service.create_invitation.assert_called_once()
        assert "invite_request_id" not in api.service.create_invitation.call_args.kwargs

        payload = _update_payload(db)
        assert payload["invitation_id"] == "inv-1"
        assert payload["status"] == "approved"
        assert payload["reviewed_by"] == "admin-1"
        assert payload["reviewed_at"]
        approval_email.assert_not_called()

    def test_link_only_updates_a_still_pending_unlinked_row(self, api):
        db = api.state["db"]
        api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        update = db.table.return_value.update.return_value
        update.eq.assert_called_once_with("id", REQUEST_ID)
        update.eq.return_value.eq.assert_called_once_with("status", "pending")
        update.eq.return_value.eq.return_value.is_.assert_called_once_with("invitation_id", "null")

    def test_without_invite_request_id_nothing_is_looked_up_or_linked(self, api):
        db = api.state["db"]
        resp = api.client.post("/api/invites/admin/club-fan", json={"club_id": 10})

        assert resp.status_code == 200
        db.table.assert_not_called()

    def test_unknown_request_is_404_and_creates_no_invite(self, api):
        api.with_db(_db(None))
        resp = api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        assert resp.status_code == 404
        api.service.create_invitation.assert_not_called()

    def test_already_linked_request_is_409(self, api):
        db = api.with_db(_db({**PENDING, "invitation_id": "inv-0"}))
        resp = api.client.post("/api/invites/admin/team-player", json=TEAM_BODY)

        assert resp.status_code == 409
        api.service.create_invitation.assert_not_called()
        db.table.return_value.update.assert_not_called()

    @pytest.mark.parametrize("status", ["approved", "rejected"])
    def test_request_that_is_no_longer_pending_is_409(self, api, status):
        api.with_db(_db({**PENDING, "status": status}))
        resp = api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        assert resp.status_code == 409
        api.service.create_invitation.assert_not_called()

    def test_malformed_request_id_is_422(self, api):
        resp = api.client.post("/api/invites/admin/club-fan", json={**CLUB_BODY, "invite_request_id": "nope"})

        assert resp.status_code == 422
        api.service.create_invitation.assert_not_called()

    def test_a_failed_link_does_not_fail_the_created_invite(self, api):
        db = api.state["db"]
        db.table.return_value.update.side_effect = Exception("db down")
        resp = api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        assert resp.status_code == 200
        assert resp.json()["id"] == "inv-1"

    def test_a_lost_race_does_not_fail_the_created_invite(self, api):
        api.with_db(_db(PENDING, linked=False))
        resp = api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        assert resp.status_code == 200


class TestAdminOnly:
    def test_club_manager_cannot_link_through_the_manager_endpoint(self, api):
        api.as_user(CLUB_MANAGER)
        resp = api.client.post("/api/invites/club-manager/club-fan", json=CLUB_BODY)

        assert resp.status_code == 403
        api.service.create_invitation.assert_not_called()
        api.state["db"].table.return_value.update.assert_not_called()

    @pytest.mark.parametrize(
        ("path", "invite_type"),
        [("/api/invites/team-manager/team-fan", "team_fan"), ("/api/invites/team-manager/team-player", "team_player")],
    )
    def test_team_manager_cannot_link(self, api, path, invite_type):
        api.as_user(TEAM_MANAGER)
        resp = api.client.post(path, json=dict(TEAM_BODY, invite_type=invite_type))

        assert resp.status_code == 403
        api.service.create_invitation.assert_not_called()

    def test_club_manager_cannot_use_the_admin_endpoint_to_link(self, api):
        api.as_user(CLUB_MANAGER)
        resp = api.client.post("/api/invites/admin/club-fan", json=CLUB_BODY)

        assert resp.status_code == 403
        api.state["db"].table.return_value.update.assert_not_called()

    def test_manager_without_invite_request_id_is_unchanged(self, api):
        api.as_user(CLUB_MANAGER)
        resp = api.client.post("/api/invites/club-manager/club-fan", json={"club_id": 10})

        assert resp.status_code == 200


class TestRequestList:
    @pytest.fixture
    def list_api(self):
        from api import invite_requests
        from auth import get_current_user_required

        app = FastAPI()
        app.include_router(invite_requests.router)
        app.dependency_overrides[get_current_user_required] = lambda: ADMIN
        return invite_requests, TestClient(app)

    def _row(self, **extra):
        return {
            "id": REQUEST_ID,
            "email": "pat@example.com",
            "name": "Pat",
            "team": None,
            "reason": None,
            "wants_ios_beta": True,
            "status": "approved",
            "created_at": "2026-10-10T00:00:00+00:00",
            "updated_at": "2026-10-10T00:00:00+00:00",
            "reviewed_by": "admin-1",
            "reviewed_at": "2026-10-10T00:00:00+00:00",
            "admin_notes": None,
            **extra,
        }

    def _db(self, rows):
        db = MagicMock()
        db.table.return_value.select.return_value.order.return_value.range.return_value.execute.return_value = (
            SimpleNamespace(data=rows)
        )
        return db

    def test_list_embeds_the_linked_invitation(self, list_api):
        module, client = list_api
        invitation = {
            "id": "inv-1",
            "invite_code": "ABCDEFGHJKLM",
            "invite_type": "club_fan",
            "status": "pending",
            "testflight_status": "failed",
            "testflight_error": "HTTP 403",
        }
        db = self._db([self._row(invitation_id="inv-1", invitation=invitation)])
        with patch.object(module, "service_client", db):
            resp = client.get("/api/invite-requests")

        assert resp.status_code == 200
        row = resp.json()[0]
        assert row["invitation_id"] == "inv-1"
        assert row["invitation"] == invitation
        select = db.table.return_value.select.call_args.args[0]
        assert "invitation:invitations(" in select
        assert "testflight_status" in select

    def test_unlinked_request_has_no_invitation(self, list_api):
        module, client = list_api
        with patch.object(module, "service_client", self._db([self._row(invitation_id=None, invitation=None)])):
            resp = client.get("/api/invite-requests")

        assert resp.json()[0]["invitation"] is None
