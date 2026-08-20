"""Admin edits to user accounts (SB-803).

PATCH /api/admin/users/{id} lets an admin fix a user's role, team or club from
the web app. Editing previously required shell access to manage_users.py, which
is no use at a match.

The interesting behaviour is not the happy path — it is the guardrails. Removing
the last admin, or your own admin role, locks people out of the only screen that
could undo it.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": "admin-1", "username": "tom", "role": "admin"}
OTHER_ADMIN = {"user_id": "admin-2", "username": "other", "role": "admin"}

TARGET_FAN = {
    "id": "u-9",
    "username": "tom_ifa_fan",
    "role": "team-fan",
    "team_id": None,
    "club_id": None,
}


def _client(actor=ADMIN):
    from app import app
    from auth import require_admin

    app.dependency_overrides[require_admin] = lambda: actor
    return TestClient(app)


def _supabase(target=TARGET_FAN, admin_rows=None):
    """Fake auth_service_client covering the table calls the endpoint makes."""
    client = MagicMock()
    tables = {}

    def table(name):
        if name not in tables:
            t = MagicMock()
            t.select.return_value = t
            t.eq.return_value = t
            t.in_.return_value = t
            t.limit.return_value = t
            t.order.return_value = t
            t.update.return_value = t
            t.insert.return_value = t
            if name == "user_profiles":
                # First execute() is the target lookup; a later one may be the
                # admin-count query. side_effect handles both in order.
                t.execute.side_effect = [
                    MagicMock(data=[target] if target else []),
                    MagicMock(data=admin_rows if admin_rows is not None else [{"id": "admin-1"}]),
                    MagicMock(data=[]),
                ]
            else:
                t.execute.return_value = MagicMock(data=[])
            tables[name] = t
        return tables[name]

    client.table.side_effect = table
    client._tables = tables
    return client


@pytest.mark.unit
class TestAdminUserUpdate:
    def teardown_method(self):
        from app import app

        app.dependency_overrides.clear()

    def test_assigns_a_team_to_a_fan_with_none(self):
        # The case that prompted this: accounts named for a club and attached
        # to nothing, unfixable from the UI.
        with (
            patch("app.auth_service_client", _supabase()),
            patch("app.team_dao") as team_dao,
        ):
            team_dao.get_team_by_id.return_value = {"id": 19, "name": "IFA"}

            response = _client().patch("/api/admin/users/u-9", json={"team_id": 19})

            assert response.status_code == 200
            assert response.json()["changes"]["team_id"] == {"from": None, "to": 19}

    def test_rejects_a_team_that_does_not_exist(self):
        with (
            patch("app.auth_service_client", _supabase()),
            patch("app.team_dao") as team_dao,
        ):
            team_dao.get_team_by_id.return_value = None

            response = _client().patch("/api/admin/users/u-9", json={"team_id": 99999})

            assert response.status_code == 400
            assert "Team not found" in response.json()["detail"]

    def test_clearing_an_assignment_is_a_real_change_not_a_no_op(self):
        # null is a meaningful value here — it is how an assignment is removed.
        # Treating "sent as null" the same as "not sent" would make clearing
        # impossible.
        assigned = {**TARGET_FAN, "team_id": 19}
        with (
            patch("app.auth_service_client", _supabase(target=assigned)),
            patch("app.team_dao"),
        ):
            response = _client().patch("/api/admin/users/u-9", json={"team_id": None})

            assert response.status_code == 200
            assert response.json()["changes"]["team_id"] == {"from": 19, "to": None}

    def test_an_admin_cannot_remove_their_own_admin_role(self):
        me = {**TARGET_FAN, "id": "admin-1", "username": "tom", "role": "admin"}
        with patch("app.auth_service_client", _supabase(target=me)):
            response = _client().patch("/api/admin/users/admin-1", json={"role": "team-fan"})

            assert response.status_code == 400
            assert "your own admin role" in response.json()["detail"]

    def test_the_last_admin_cannot_be_demoted(self):
        target = {**TARGET_FAN, "id": "admin-2", "username": "other", "role": "admin"}
        with patch("app.auth_service_client", _supabase(target=target, admin_rows=[{"id": "admin-2"}])):
            response = _client().patch("/api/admin/users/admin-2", json={"role": "team-fan"})

            assert response.status_code == 400
            assert "last admin" in response.json()["detail"]

    def test_another_admin_can_be_demoted_when_others_remain(self):
        target = {**TARGET_FAN, "id": "admin-2", "username": "other", "role": "admin"}
        admins = [{"id": "admin-1"}, {"id": "admin-2"}]
        with patch("app.auth_service_client", _supabase(target=target, admin_rows=admins)):
            response = _client().patch("/api/admin/users/admin-2", json={"role": "team-fan"})

            assert response.status_code == 200

    def test_unknown_user_is_404(self):
        with patch("app.auth_service_client", _supabase(target=None)):
            response = _client().patch("/api/admin/users/nope", json={"role": "team-fan"})

            assert response.status_code == 404

    def test_empty_payload_is_rejected(self):
        with patch("app.auth_service_client", _supabase()):
            response = _client().patch("/api/admin/users/u-9", json={})

            assert response.status_code == 400

    def test_writes_an_audit_row_naming_actor_and_target(self):
        # A privilege change with no record of who made it is the part of this
        # feature that would be hard to live with.
        fake = _supabase()
        with (
            patch("app.auth_service_client", fake),
            patch("app.team_dao") as team_dao,
        ):
            team_dao.get_team_by_id.return_value = {"id": 19, "name": "IFA"}
            _client().patch("/api/admin/users/u-9", json={"team_id": 19})

            audit = fake._tables["admin_user_audit_log"]
            audit.insert.assert_called_once()
            row = audit.insert.call_args[0][0]
            assert row["actor_username"] == "tom"
            assert row["target_username"] == "tom_ifa_fan"
            assert row["changes"]["team_id"] == {"from": None, "to": 19}

    def test_a_failed_audit_write_does_not_discard_the_update(self):
        fake = _supabase()
        with (
            patch("app.auth_service_client", fake),
            patch("app.team_dao") as team_dao,
        ):
            team_dao.get_team_by_id.return_value = {"id": 19, "name": "IFA"}
            fake.table("admin_user_audit_log").insert.side_effect = RuntimeError("audit down")

            response = _client().patch("/api/admin/users/u-9", json={"team_id": 19})

            # The profile write already happened; failing the request would
            # report a false negative and invite a duplicate retry.
            assert response.status_code == 200
