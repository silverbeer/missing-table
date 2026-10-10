"""iPhone beta invites: TestFlight from the admin invite flow (SB-1314).

The App Store Connect client is mocked throughout — these tests are about what
the invite flow does with its result: record it, never fail the invite on it,
keep it admin-only, and tell the invitee what to expect from Apple.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.testflight_client import TesterResult

pytestmark = [pytest.mark.unit, pytest.mark.backend]

ROW = {"id": "inv-1", "invite_code": "ABCDEFGHJKLM", "invite_type": "club_fan", "club_id": 10}


def _supabase(row=None):
    """MagicMock client: invite codes are unique, the insert returns `row`."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    client.table.return_value.insert.return_value.execute.return_value.data = [dict(row or ROW)]
    return client


def _inserted(client) -> dict:
    return client.table.return_value.insert.call_args.args[0]


def _updates(client) -> list[dict]:
    return [c.args[0] for c in client.table.return_value.update.call_args_list]


def _create(client, **kwargs):
    from services.invite_service import InviteService

    return InviteService(client).create_invitation(
        invited_by_user_id="admin-1", invite_type="club_fan", club_id=10, **kwargs
    )


class TestCreateInvitation:
    def test_not_requested_never_touches_testflight(self):
        client = _supabase()
        with patch("services.testflight_client.add_tester") as add:
            result = _create(client, email="a@example.com")

        add.assert_not_called()
        assert "testflight_status" not in _inserted(client)
        assert "testflight_status" not in result

    def test_added_is_recorded_on_the_invitation(self):
        client = _supabase()
        with patch(
            "services.testflight_client.add_tester",
            return_value=TesterResult(status="added", tester_id="t-1"),
        ) as add:
            result = _create(client, ios_beta=True, testflight_email="apple@icloud.com")

        add.assert_called_once_with("apple@icloud.com", None, None)
        assert _inserted(client)["testflight_status"] == "pending"
        assert _inserted(client)["testflight_email"] == "apple@icloud.com"
        assert {"testflight_status": "added", "testflight_error": None, "testflight_tester_id": "t-1"} in _updates(
            client
        )
        assert result["testflight_status"] == "added"
        assert result["testflight_tester_id"] == "t-1"

    def test_testflight_email_defaults_to_the_invite_email(self):
        client = _supabase()
        with patch(
            "services.testflight_client.add_tester",
            return_value=TesterResult(status="added", tester_id="t-1"),
        ) as add:
            _create(client, email="a@example.com", ios_beta=True)

        assert add.call_args.args[0] == "a@example.com"
        assert _inserted(client)["testflight_email"] == "a@example.com"

    def test_ios_beta_without_any_email_is_refused(self):
        client = _supabase()
        with pytest.raises(ValueError, match="TestFlight email"):
            _create(client, ios_beta=True)
        client.table.return_value.insert.assert_not_called()

    def test_failure_does_not_fail_the_invite(self):
        client = _supabase()
        with patch(
            "services.testflight_client.add_tester",
            return_value=TesterResult(status="failed", error="HTTP 403: nope"),
        ):
            result = _create(client, ios_beta=True, testflight_email="apple@icloud.com")

        assert result["invite_code"] == ROW["invite_code"]
        assert result["testflight_status"] == "failed"
        assert result["testflight_error"] == "HTTP 403: nope"

    def test_an_exception_from_the_client_does_not_fail_the_invite(self):
        client = _supabase()
        with patch("services.testflight_client.add_tester", side_effect=RuntimeError("boom")):
            result = _create(client, ios_beta=True, testflight_email="apple@icloud.com")

        assert result["testflight_status"] == "failed"
        assert "boom" in result["testflight_error"]

    def test_failing_to_record_the_result_does_not_fail_the_invite(self):
        client = _supabase()
        client.table.return_value.update.side_effect = Exception("column does not exist")
        with patch(
            "services.testflight_client.add_tester",
            return_value=TesterResult(status="added", tester_id="t-1"),
        ):
            result = _create(client, ios_beta=True, testflight_email="apple@icloud.com")

        assert result["testflight_status"] == "added"

    def test_the_email_gets_the_ios_section_flag(self):
        client = _supabase()
        with (
            patch(
                "services.testflight_client.add_tester",
                return_value=TesterResult(status="added", tester_id="t-1"),
            ),
            patch("services.email_service.EmailService") as email_cls,
        ):
            _create(client, email="a@example.com", ios_beta=True, testflight_email="apple@icloud.com")

        kwargs = email_cls.return_value.send_invitation.call_args.kwargs
        assert kwargs["ios_beta"] is True
        assert kwargs["testflight_email"] == "apple@icloud.com"


class TestRetry:
    def _service(self, row):
        from services.invite_service import InviteService

        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [row] if row else []
        return InviteService(client), client

    def test_retry_re_adds_and_records(self):
        service, client = self._service(
            {"id": "inv-1", "testflight_status": "failed", "testflight_email": "apple@icloud.com"}
        )
        with patch(
            "services.testflight_client.add_tester",
            return_value=TesterResult(status="added", tester_id="t-1"),
        ) as add:
            result = service.retry_testflight("inv-1")

        assert add.call_args.args[0] == "apple@icloud.com"
        assert result["testflight_status"] == "added"
        assert _updates(client)[0]["testflight_status"] == "added"

    def test_retry_of_an_invite_that_never_asked_is_refused(self):
        service, _ = self._service({"id": "inv-1", "testflight_status": None})
        with pytest.raises(ValueError):
            service.retry_testflight("inv-1")

    def test_retry_of_a_missing_invite_is_a_lookup_error(self):
        service, _ = self._service(None)
        with pytest.raises(LookupError):
            service.retry_testflight("nope")


class TestRemoveForDeletedUser:
    def _service(self, rows):
        from services.invite_service import InviteService

        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = rows
        return InviteService(client), client

    def test_removes_added_testers_and_marks_them_removed(self):
        service, client = self._service([{"id": "inv-1", "testflight_tester_id": "t-1"}])
        with patch(
            "services.testflight_client.remove_tester",
            return_value=TesterResult(status="removed", tester_id="t-1"),
        ) as remove:
            assert service.remove_testflight_for_user("u-1") == 1

        remove.assert_called_once_with("t-1")
        assert _updates(client) == [{"testflight_status": "removed", "testflight_error": None}]

    def test_a_failed_removal_is_recorded_and_not_raised(self):
        service, client = self._service([{"id": "inv-1", "testflight_tester_id": "t-1"}])
        with patch(
            "services.testflight_client.remove_tester",
            return_value=TesterResult(status="failed", error="HTTP 500"),
        ):
            assert service.remove_testflight_for_user("u-1") == 0

        assert _updates(client) == [{"testflight_error": "remove failed: HTTP 500"}]

    def test_no_beta_invites_means_no_apple_call(self):
        service, _ = self._service([])
        with patch("services.testflight_client.remove_tester") as remove:
            assert service.remove_testflight_for_user("u-1") == 0
        remove.assert_not_called()

    def test_a_lookup_failure_is_swallowed(self):
        from services.invite_service import InviteService

        client = MagicMock()
        client.table.side_effect = Exception("db down")
        assert InviteService(client).remove_testflight_for_user("u-1") == 0


class TestInvitationEmail:
    @pytest.fixture
    def sent(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
        from services.email_service import EmailService

        payloads: list[dict] = []
        with patch("resend.Emails.send", side_effect=lambda p: payloads.append(p) or {"id": "x"}):
            yield EmailService(), payloads

    def test_no_ios_section_unless_requested(self, sent):
        service, payloads = sent
        service.send_invitation("a@example.com", "ABCDEFGHJKLM", "club_fan")
        assert "TestFlight" not in payloads[0]["text"]
        assert "TestFlight" not in payloads[0]["html"]

    def test_ios_section_names_the_testflight_address(self, sent):
        service, payloads = sent
        service.send_invitation(
            "a@example.com", "ABCDEFGHJKLM", "club_fan", ios_beta=True, testflight_email="apple@icloud.com"
        )
        text = payloads[0]["text"]
        assert "iPhone app (beta)" in text
        assert "Apple TestFlight sent to apple@icloud.com" in text
        assert "Install TestFlight" in text
        assert "sign up with this code: ABCDEFGHJKLM" in text
        assert "apple@icloud.com" in payloads[0]["html"]

    def test_ios_section_falls_back_to_the_invite_address(self, sent):
        service, payloads = sent
        service.send_invitation("a@example.com", "ABCDEFGHJKLM", "club_fan", ios_beta=True)
        assert "TestFlight sent to a@example.com" in payloads[0]["text"]


ADMIN = {"id": "admin-1", "user_id": "admin-1", "role": "admin"}
CLUB_MANAGER = {"id": "cm-1", "user_id": "cm-1", "role": "club_manager", "club_id": 10}
TEAM_MANAGER = {"id": "tm-1", "user_id": "tm-1", "role": "team_manager"}

TEAM_BODY = {"invite_type": "team_player", "team_id": 5, "age_group_id": 3, "ios_beta": True}


@pytest.fixture
def api(monkeypatch):
    from api import invites
    from auth import get_current_user_required

    app = FastAPI()
    app.include_router(invites.router)
    user = {"value": ADMIN}
    app.dependency_overrides[get_current_user_required] = lambda: user["value"]

    service = MagicMock()
    service.create_invitation.return_value = {"id": "inv-1"}
    service.retry_testflight.return_value = {"id": "inv-1", "testflight_status": "added"}
    monkeypatch.setattr(invites, "InviteService", lambda _client: service)
    manager_service = MagicMock()
    manager_service.can_manage_team.return_value = True
    monkeypatch.setattr(invites, "TeamManagerService", lambda _client: manager_service)
    monkeypatch.setattr(invites, "service_client", MagicMock())

    def as_user(u):
        user["value"] = u

    return TestClient(app), service, as_user


class TestApiRoles:
    def test_admin_endpoint_passes_ios_beta_through(self, api):
        client, service, _ = api
        resp = client.post(
            "/api/invites/admin/club-fan",
            json={"club_id": 10, "email": "a@example.com", "ios_beta": True, "testflight_email": "apple@icloud.com"},
        )
        assert resp.status_code == 200
        kwargs = service.create_invitation.call_args.kwargs
        assert kwargs["ios_beta"] is True
        assert kwargs["testflight_email"] == "apple@icloud.com"

    def test_club_manager_cannot_set_ios_beta(self, api):
        client, service, as_user = api
        as_user(CLUB_MANAGER)
        resp = client.post("/api/invites/club-manager/club-fan", json={"club_id": 10, "ios_beta": True})
        assert resp.status_code == 403
        service.create_invitation.assert_not_called()

    @pytest.mark.parametrize("path", ["/api/invites/team-manager/team-fan", "/api/invites/team-manager/team-player"])
    def test_team_manager_cannot_set_ios_beta(self, api, path):
        client, service, as_user = api
        as_user(TEAM_MANAGER)
        body = dict(TEAM_BODY, invite_type="team_fan" if path.endswith("fan") else "team_player")
        resp = client.post(path, json=body)
        assert resp.status_code == 403
        service.create_invitation.assert_not_called()

    def test_club_manager_without_ios_beta_is_unchanged(self, api):
        client, service, as_user = api
        as_user(CLUB_MANAGER)
        resp = client.post("/api/invites/club-manager/club-fan", json={"club_id": 10})
        assert resp.status_code == 200
        assert "ios_beta" not in service.create_invitation.call_args.kwargs

    def test_club_manager_cannot_use_the_admin_endpoint(self, api):
        client, _, as_user = api
        as_user(CLUB_MANAGER)
        resp = client.post("/api/invites/admin/club-fan", json={"club_id": 10, "ios_beta": True})
        assert resp.status_code == 403

    def test_retry_is_admin_only(self, api):
        client, service, as_user = api
        as_user(CLUB_MANAGER)
        resp = client.post("/api/invites/admin/inv-1/testflight/retry")
        assert resp.status_code == 403
        service.retry_testflight.assert_not_called()

    def test_admin_retry_returns_the_new_status(self, api):
        client, service, _ = api
        resp = client.post("/api/invites/admin/inv-1/testflight/retry")
        assert resp.status_code == 200
        assert resp.json()["testflight_status"] == "added"
        service.retry_testflight.assert_called_once_with("inv-1")

    def test_retry_of_a_missing_invite_is_404(self, api):
        client, service, _ = api
        service.retry_testflight.side_effect = LookupError("Invitation not found")
        resp = client.post("/api/invites/admin/nope/testflight/retry")
        assert resp.status_code == 404
