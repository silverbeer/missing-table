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
    from auth import get_current_user_optional, require_admin

    dao = MagicMock()
    dao.set_for_match.return_value = PICK
    app_module.app.dependency_overrides[require_admin] = lambda: ADMIN
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
