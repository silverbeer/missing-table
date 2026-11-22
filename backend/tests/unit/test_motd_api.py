"""Tournament Match of the Day endpoints (SB-1559), one pick per age group (SB-1750).

The real app with auth overridden and motd_dao mocked: these pin the status
codes — 200 with null for an unpicked slot, 400 for a pick that cannot be true,
404 for an unknown match — without a database.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": "admin-1", "username": "admin", "role": "admin"}
PICK = {"tournament_id": 12, "match_date": "2026-12-04", "age_group_id": 3, "match": {"id": 501}, "reasons": None}
U16_PICK = {**PICK, "age_group_id": 4, "match": {"id": 502}}


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
        dao.list_for_day.return_value = []
        r = http.get("/api/tournaments/12/motd", params={"date": "2026-12-04"})
        assert r.status_code == 200
        assert r.json() == {"tournament_id": 12, "match_date": "2026-12-04", "motd": None, "picks": []}

    def test_a_single_age_tournament_reads_its_day_without_an_age_group(self, client):
        # The legacy call: one pick that day, and `motd` is it.
        http, dao = client
        dao.list_for_day.return_value = [PICK]
        r = http.get("/api/tournaments/12/motd", params={"date": "2026-12-04"})
        assert r.status_code == 200
        assert r.json()["motd"] == PICK
        assert r.json()["picks"] == [PICK]

    def test_an_age_group_gets_its_own_pick(self, client):
        http, dao = client
        dao.list_for_day.return_value = [PICK, U16_PICK]
        r = http.get("/api/tournaments/12/motd", params={"date": "2026-12-04", "age_group_id": 4})
        assert r.json()["motd"] == U16_PICK
        assert r.json()["picks"] == [PICK, U16_PICK]

    def test_an_age_group_with_no_pick_is_200_with_null_not_another_ages_pick(self, client):
        http, dao = client
        dao.list_for_day.return_value = [PICK]
        r = http.get("/api/tournaments/12/motd", params={"date": "2026-12-04", "age_group_id": 4})
        assert r.status_code == 200
        assert r.json()["motd"] is None

    def test_without_a_date_lists_every_pick(self, client):
        http, dao = client
        dao.list_for_tournament.return_value = [PICK, U16_PICK]
        r = http.get("/api/tournaments/12/motd")
        assert r.status_code == 200
        assert r.json()["picks"] == [PICK, U16_PICK]

    def test_without_a_date_an_age_group_narrows_the_list(self, client):
        http, dao = client
        dao.list_for_tournament.return_value = [PICK, U16_PICK]
        r = http.get("/api/tournaments/12/motd", params={"age_group_id": 4})
        assert r.json()["picks"] == [U16_PICK]

    def test_a_bad_date_is_400(self, client):
        http, _ = client
        assert http.get("/api/tournaments/12/motd", params={"date": "Dec 4"}).status_code == 400

    def test_anonymous_viewers_never_see_test_matches(self, client):
        http, dao = client
        dao.list_for_day.return_value = []
        http.get("/api/tournaments/12/motd", params={"date": "2026-12-04"})
        assert dao.list_for_day.call_args.kwargs["include_test"] is False


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

    def test_without_an_age_group_the_pick_is_made_unguarded(self, client):
        # Existing callers send no age group; the slot comes from the match.
        http, dao = client
        dao.set_for_match.return_value = PICK
        r = http.post("/api/admin/tournaments/12/motd", json={"match_id": 501})
        assert r.status_code == 200
        assert r.json()["age_group_id"] == 3
        assert dao.set_for_match.call_args.kwargs["age_group_id"] is None

    def test_a_given_age_group_is_passed_as_the_guard(self, client):
        http, dao = client
        dao.set_for_match.return_value = PICK
        http.post("/api/admin/tournaments/12/motd", json={"match_id": 501, "age_group_id": 3})
        assert dao.set_for_match.call_args.kwargs["age_group_id"] == 3

    def test_a_mismatched_age_group_is_400(self, client):
        from dao.motd_dao import MotdPickError

        http, dao = client
        dao.set_for_match.side_effect = MotdPickError("Match 501 is in age group 3, not 4")
        r = http.post("/api/admin/tournaments/12/motd", json={"match_id": 501, "age_group_id": 4})
        assert r.status_code == 400
        assert "age group" in r.json()["detail"]

    def test_a_match_without_an_age_group_is_400(self, client):
        from dao.motd_dao import MotdPickError

        http, dao = client
        dao.set_for_match.side_effect = MotdPickError("Match 501 has no age group, so it cannot be Match of the Day")
        r = http.post("/api/admin/tournaments/12/motd", json={"match_id": 501})
        assert r.status_code == 400
        assert "no age group" in r.json()["detail"]

    def test_a_failed_write_is_500_with_a_generic_message(self, client):
        from dao.motd_dao import MotdWriteError

        http, dao = client
        dao.set_for_match.side_effect = MotdWriteError("Could not store match of the day")
        r = http.post("/api/admin/tournaments/12/motd", json={"match_id": 501})
        assert r.status_code == 500
        assert r.json()["detail"] == "Could not set match of the day"

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
        dao.clear_day.return_value = 0
        r = http.delete("/api/admin/tournaments/12/motd/2026-12-04")
        assert r.status_code == 200
        assert r.json() == {"tournament_id": 12, "match_date": "2026-12-04", "age_group_id": None, "cleared": 0}

    def test_without_an_age_group_the_whole_day_is_cleared(self, client):
        http, dao = client
        dao.clear_day.return_value = 2
        r = http.delete("/api/admin/tournaments/12/motd/2026-12-04")
        assert r.json()["cleared"] == 2
        assert dao.clear_day.call_args.kwargs["age_group_id"] is None

    def test_with_an_age_group_only_that_slot_is_cleared(self, client):
        http, dao = client
        dao.clear_day.return_value = 1
        r = http.delete("/api/admin/tournaments/12/motd/2026-12-04", params={"age_group_id": 4})
        assert r.status_code == 200
        assert r.json() == {"tournament_id": 12, "match_date": "2026-12-04", "age_group_id": 4, "cleared": 1}
        dao.clear_day.assert_called_once_with(12, "2026-12-04", age_group_id=4)

    def test_a_failed_delete_is_500_with_a_generic_message_not_cleared_zero(self, client):
        from dao.motd_dao import MotdWriteError

        http, dao = client
        dao.clear_day.side_effect = MotdWriteError("Could not clear match of the day")
        r = http.delete("/api/admin/tournaments/12/motd/2026-12-04", params={"age_group_id": 4})
        assert r.status_code == 500
        assert r.json() == {"detail": "Could not clear match of the day"}
