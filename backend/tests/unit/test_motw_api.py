"""Match of the Week endpoints — reasons (SB-1552).

The real app with auth overridden and motw_dao mocked: these pin how the POST
body's `reasons` reaches the DAO — omitted, null, [] and populated are four
different instructions — without a database.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
PICK = {"week_start": "2026-11-02", "match": {"id": 4093}, "blurb": None, "reasons": None}


@pytest.fixture
def client():
    import app as app_module
    from auth import get_current_user_optional, require_admin, require_motw_editor

    dao = MagicMock()
    dao.set_for_match.return_value = PICK
    app_module.app.dependency_overrides[require_admin] = lambda: ADMIN
    app_module.app.dependency_overrides[require_motw_editor] = lambda: ADMIN
    app_module.app.dependency_overrides[get_current_user_optional] = lambda: None
    with patch.object(app_module, "motw_dao", dao):
        yield TestClient(app_module.app), dao, app_module
    app_module.app.dependency_overrides.clear()


@pytest.mark.unit
class TestSetReasons:
    def test_omitted_reasons_ask_the_dao_to_keep_them(self, client):
        http, dao, app_module = client
        r = http.post("/api/admin/motw", json={"match_id": 4093, "blurb": "x"})
        assert r.status_code == 200
        assert dao.set_for_match.call_args.kwargs["reasons"] is app_module.MOTW_KEEP_REASONS

    def test_null_reasons_clear(self, client):
        http, dao, _ = client
        http.post("/api/admin/motw", json={"match_id": 4093, "reasons": None})
        assert dao.set_for_match.call_args.kwargs["reasons"] is None

    def test_empty_reasons_are_recorded_as_empty(self, client):
        http, dao, _ = client
        http.post("/api/admin/motw", json={"match_id": 4093, "reasons": []})
        assert dao.set_for_match.call_args.kwargs["reasons"] == []

    def test_populated_reasons_pass_through_with_kind(self, client):
        http, dao, _ = client
        http.post(
            "/api/admin/motw",
            json={"match_id": 4093, "reasons": [{"text": "1st vs 3rd", "kind": "standings"}, {"text": "Unbeaten"}]},
        )
        assert dao.set_for_match.call_args.kwargs["reasons"] == [
            {"text": "1st vs 3rd", "kind": "standings"},
            {"text": "Unbeaten", "kind": None},
        ]

    def test_more_than_six_reasons_is_422(self, client):
        http, dao, _ = client
        r = http.post("/api/admin/motw", json={"match_id": 4093, "reasons": [{"text": f"r{i}"} for i in range(7)]})
        assert r.status_code == 422
        dao.set_for_match.assert_not_called()

    def test_a_blank_reason_is_422(self, client):
        http, _, _ = client
        assert http.post("/api/admin/motw", json={"match_id": 4093, "reasons": [{"text": ""}]}).status_code == 422

    def test_unknown_match_is_404(self, client):
        http, dao, _ = client
        dao.set_for_match.return_value = None
        assert http.post("/api/admin/motw", json={"match_id": 9}).status_code == 404


@pytest.mark.unit
class TestReadReasons:
    def test_get_returns_reasons(self, client):
        http, dao, _ = client
        reasons = [{"text": "1st vs 3rd", "kind": "standings"}]
        dao.get_for_week.return_value = {**PICK, "reasons": reasons}
        r = http.get("/api/motw", params={"week_start": "2026-11-02"})
        assert r.status_code == 200
        assert r.json()["motw"]["reasons"] == reasons


MOTW_AGENT = {
    "service_id": "service-motw-agent",
    "service_name": "motw-agent",
    "permissions": ["manage_motw"],
    "role": "service_account",
    "is_service_account": True,
}
SCRAPER = {**MOTW_AGENT, "service_name": "match-scraper", "permissions": ["manage_matches"]}


@pytest.fixture
def as_caller():
    """The real role checks, with the authenticated caller swapped in."""
    import app as app_module
    from auth import get_current_user_optional, get_current_user_required

    dao = MagicMock()
    dao.set_for_match.return_value = PICK
    dao.clear_week.return_value = True
    caller: dict = {}
    app_module.app.dependency_overrides[get_current_user_required] = lambda: caller["user"]
    app_module.app.dependency_overrides[get_current_user_optional] = lambda: None

    def use(user):
        caller["user"] = user
        return TestClient(app_module.app), dao

    with patch.object(app_module, "motw_dao", dao):
        yield use
    app_module.app.dependency_overrides.clear()


@pytest.mark.unit
class TestMotwServiceAccount:
    """SB-1553: the MOTW agent's account may pick the Match of the Week, and nothing else."""

    def test_agent_can_pick(self, as_caller):
        http, dao = as_caller(MOTW_AGENT)
        r = http.post("/api/admin/motw", json={"match_id": 4093, "blurb": "x", "reasons": []})
        assert r.status_code == 200
        kwargs = dao.set_for_match.call_args.kwargs
        assert kwargs["selected_by"] is None
        assert kwargs["selected_by_service"] == "motw-agent"

    def test_admin_pick_records_the_user_not_a_service(self, as_caller):
        http, dao = as_caller(ADMIN)
        assert http.post("/api/admin/motw", json={"match_id": 4093}).status_code == 200
        kwargs = dao.set_for_match.call_args.kwargs
        assert kwargs["selected_by"] == "admin-1"
        assert kwargs["selected_by_service"] is None

    def test_agent_cannot_clear_a_week(self, as_caller):
        http, dao = as_caller(MOTW_AGENT)
        assert http.delete("/api/admin/motw/2026-11-02").status_code == 403
        dao.clear_week.assert_not_called()

    def test_agent_refused_on_admin_routes(self, as_caller):
        http, _ = as_caller(MOTW_AGENT)
        assert http.get("/api/admin/coverage").status_code == 403

    def test_agent_refused_on_match_management(self, as_caller):
        """require_admin_or_service_account wants manage_matches, which the agent lacks."""
        from fastapi import HTTPException

        from auth import require_admin_or_service_account

        with pytest.raises(HTTPException) as exc:
            require_admin_or_service_account(MOTW_AGENT)
        assert exc.value.status_code == 403

    def test_other_service_accounts_cannot_pick(self, as_caller):
        http, dao = as_caller(SCRAPER)
        assert http.post("/api/admin/motw", json={"match_id": 4093}).status_code == 403
        dao.set_for_match.assert_not_called()

    def test_ordinary_users_cannot_pick(self, as_caller):
        http, dao = as_caller({"user_id": "u1", "role": "team-manager"})
        assert http.post("/api/admin/motw", json={"match_id": 4093}).status_code == 403
        dao.set_for_match.assert_not_called()


@pytest.mark.unit
class TestCanSetMotw:
    def test_rules(self):
        from auth import can_set_motw

        assert can_set_motw(ADMIN)
        assert can_set_motw(MOTW_AGENT)
        assert not can_set_motw(SCRAPER)
        assert not can_set_motw({"role": "service_account"})
        assert not can_set_motw({"role": "team-manager", "permissions": ["manage_motw"]})
        assert not can_set_motw(None)
