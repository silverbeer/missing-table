"""Tournament Match of the Day endpoints (SB-1559).

The real app with auth overridden and motd_dao mocked: these pin the status
codes — 200 with null for an unpicked day, 400 for a pick that cannot be true,
404 for an unknown match — without a database.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
PICK = {"tournament_id": 12, "match_date": "2026-12-04", "match": {"id": 501}, "reasons": None}


@pytest.fixture
def client():
    import app as app_module
    from auth import get_current_user_optional, require_admin

    dao = MagicMock()
    app_module.app.dependency_overrides[require_admin] = lambda: ADMIN
    app_module.app.dependency_overrides[get_current_user_optional] = lambda: None
    with patch.object(app_module, "motd_dao", dao):
        yield TestClient(app_module.app), dao
    app_module.app.dependency_overrides.clear()


@pytest.mark.unit
class TestRead:
    def test_an_unpicked_day_is_200_with_null(self, client):
        http, dao = client
        dao.get_for_day.return_value = None
        r = http.get("/api/tournaments/12/motd", params={"date": "2026-12-04"})
        assert r.status_code == 200
        assert r.json() == {"tournament_id": 12, "match_date": "2026-12-04", "motd": None}

    def test_without_a_date_lists_every_pick(self, client):
        http, dao = client
        dao.list_for_tournament.return_value = [PICK]
        r = http.get("/api/tournaments/12/motd")
        assert r.status_code == 200
        assert r.json()["picks"] == [PICK]

    def test_a_bad_date_is_400(self, client):
        http, _ = client
        assert http.get("/api/tournaments/12/motd", params={"date": "Dec 4"}).status_code == 400

    def test_anonymous_viewers_never_see_test_matches(self, client):
        http, dao = client
        dao.get_for_day.return_value = None
        http.get("/api/tournaments/12/motd", params={"date": "2026-12-04"})
        assert dao.get_for_day.call_args.kwargs["include_test"] is False


@pytest.mark.unit
class TestSet:
    def test_sets_the_pick_with_reasons_and_provenance(self, client):
        http, dao = client
        dao.set_for_match.return_value = PICK
        body = {"match_id": 501, "blurb": "Big one", "reasons": [{"text": "1st vs 2nd", "kind": "table"}]}
        r = http.post("/api/admin/tournaments/12/motd", json=body)
        assert r.status_code == 200
        kwargs = dao.set_for_match.call_args.kwargs
        assert kwargs["reasons"] == [{"text": "1st vs 2nd", "kind": "table"}]
        assert kwargs["selected_by"] == "admin-1"

    def test_omitted_reasons_stay_none_and_empty_stays_empty(self, client):
        http, dao = client
        dao.set_for_match.return_value = PICK
        http.post("/api/admin/tournaments/12/motd", json={"match_id": 501})
        assert dao.set_for_match.call_args.kwargs["reasons"] is None
        http.post("/api/admin/tournaments/12/motd", json={"match_id": 501, "reasons": []})
        assert dao.set_for_match.call_args.kwargs["reasons"] == []

    def test_an_unknown_match_is_404(self, client):
        http, dao = client
        dao.set_for_match.return_value = None
        assert http.post("/api/admin/tournaments/12/motd", json={"match_id": 999}).status_code == 404

    def test_a_match_from_another_tournament_is_400(self, client):
        from dao.motd_dao import MotdPickError

        http, dao = client
        dao.set_for_match.side_effect = MotdPickError("Match 501 is not in tournament 12")
        r = http.post("/api/admin/tournaments/12/motd", json={"match_id": 501})
        assert r.status_code == 400
        assert "not in tournament" in r.json()["detail"]

    def test_too_many_reasons_is_rejected(self, client):
        http, _ = client
        reasons = [{"text": f"r{i}"} for i in range(7)]
        assert (
            http.post("/api/admin/tournaments/12/motd", json={"match_id": 501, "reasons": reasons}).status_code == 422
        )


@pytest.mark.unit
class TestClear:
    def test_clear_is_idempotent(self, client):
        http, dao = client
        dao.clear_day.return_value = False
        r = http.delete("/api/admin/tournaments/12/motd/2026-12-04")
        assert r.status_code == 200
        assert r.json() == {"tournament_id": 12, "match_date": "2026-12-04", "cleared": False}
