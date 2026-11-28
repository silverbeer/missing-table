"""Admin merge + logo-gap endpoints with the DAO mocked (SB-1822, SB-1815)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

ADMIN = {"user_id": "admin-1", "username": "tom", "role": "admin"}
FAN = {"user_id": "u-1", "username": "fan", "role": "user"}

SECRET = 'duplicate key value violates constraint "teams_pkey" (SQLSTATE 23505) in public.merge_team'

TEAM_URL = "/api/admin/teams/{}/merge-into/{}"
CLUB_URL = "/api/admin/clubs/{}/merge-into/{}"


def _pg_error(code, message):
    """What supabase-py raises for a function's RAISE: the SQLSTATE is `.code`."""
    return APIError({"code": code, "message": message, "details": None, "hint": None})


def _client(actor=ADMIN):
    """Real require_admin on a bearer token resolved to `actor`."""
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: actor
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    from app import app

    app.dependency_overrides.clear()


@pytest.mark.unit
class TestAdminRequired:
    @pytest.mark.parametrize(
        ("method", "url"),
        [
            ("post", TEAM_URL.format(1, 2)),
            ("post", CLUB_URL.format(1, 2)),
            ("get", "/api/admin/clubs/logo-gaps"),
        ],
    )
    def test_non_admin_forbidden(self, method, url):
        client = _client(FAN)
        with patch("app.team_dao") as t, patch("app.club_dao") as c:
            resp = getattr(client, method)(url)
        assert resp.status_code == 403
        t.merge_team.assert_not_called()
        c.merge_club.assert_not_called()
        c.logo_gaps.assert_not_called()


@pytest.mark.unit
class TestMergeTeam:
    def test_dry_run_is_the_default(self):
        with patch("app.team_dao") as dao:
            dao.merge_team.return_value = {"dry_run": True, "tables": {}, "blockers": []}
            resp = _client().post(TEAM_URL.format(1, 2))
        assert resp.status_code == 200
        dao.merge_team.assert_called_once_with(1, 2, dry_run=True)

    def test_explicit_real_run(self):
        with patch("app.team_dao") as dao:
            dao.merge_team.return_value = {"dry_run": False, "tables": {}, "alias": "added"}
            resp = _client().post(TEAM_URL.format(1, 2) + "?dry_run=false")
        assert resp.status_code == 200
        assert resp.json()["alias"] == "added"
        dao.merge_team.assert_called_once_with(1, 2, dry_run=False)

    def test_same_id_is_400_without_calling_dao(self):
        with patch("app.team_dao") as dao:
            resp = _client().post(TEAM_URL.format(5, 5))
        assert resp.status_code == 400
        dao.merge_team.assert_not_called()

    @pytest.mark.parametrize(
        ("raised", "status"),
        [
            (_pg_error("MTNF1", "merge_team: team 9 does not exist"), 404),
            (_pg_error("MTBLK", "merge_team: 2 blocker(s), run a dry run to list them"), 409),
            (_pg_error("MTSAM", "merge_team: source and target must be two different teams"), 400),
            (_pg_error("23505", SECRET), 500),
            (Exception(SECRET), 500),
        ],
    )
    def test_error_mapping_hides_implementation(self, raised, status):
        with patch("app.team_dao") as dao:
            dao.merge_team.side_effect = raised
            resp = _client().post(TEAM_URL.format(1, 2) + "?dry_run=false")
        assert resp.status_code == status
        body = resp.text.lower()
        for leak in ("merge_team", "sqlstate", "teams_pkey", "public.", "constraint"):
            assert leak not in body

    @pytest.mark.parametrize(
        "message",
        [
            'relation "public.zz" does not exist',
            "merge_team: 2 blocker(s), run a dry run to list them",
            "source and target must be two different teams",
        ],
    )
    def test_wording_alone_is_not_a_refusal(self, message):
        # Only the functions' own SQLSTATEs map to 4xx; text that merely looks
        # like one (an unrelated "does not exist") is an unexpected failure.
        with patch("app.team_dao") as dao, patch("app.logger") as log:
            dao.merge_team.side_effect = _pg_error("42P01", message)
            resp = _client().post(TEAM_URL.format(1, 2) + "?dry_run=false")
        assert resp.status_code == 500
        log.error.assert_called_once()

    def test_incomplete_dry_run_is_returned_and_logged(self):
        error = {"sqlstate": "23514", "table": "matches", "constraint": "matches_check"}
        with patch("app.team_dao") as dao, patch("app.logger") as log:
            dao.merge_team.return_value = {
                "dry_run": True,
                "tables": {},
                "blockers": [],
                "complete": False,
                "error": error,
            }
            resp = _client().post(TEAM_URL.format(1, 2))
        assert resp.status_code == 200
        assert resp.json()["error"] == error
        log.warning.assert_called_once()
        assert log.warning.call_args.kwargs["error"] == error

    def test_complete_dry_run_logs_nothing(self):
        with patch("app.team_dao") as dao, patch("app.logger") as log:
            dao.merge_team.return_value = {
                "dry_run": True,
                "tables": {},
                "blockers": [],
                "complete": True,
                "error": None,
            }
            _client().post(TEAM_URL.format(1, 2))
        log.warning.assert_not_called()


@pytest.mark.unit
class TestMergeClub:
    def test_dry_run_is_the_default(self):
        with patch("app.club_dao") as dao:
            dao.merge_club.return_value = {"dry_run": True, "tables": {}, "blockers": [], "copied": []}
            resp = _client().post(CLUB_URL.format(3, 4))
        assert resp.status_code == 200
        dao.merge_club.assert_called_once_with(3, 4, dry_run=True)

    def test_real_run(self):
        with patch("app.club_dao") as dao:
            dao.merge_club.return_value = {"dry_run": False, "tables": {}, "copied": ["logo_url"]}
            resp = _client().post(CLUB_URL.format(3, 4) + "?dry_run=false")
        assert resp.status_code == 200
        dao.merge_club.assert_called_once_with(3, 4, dry_run=False)

    def test_same_id_is_400(self):
        with patch("app.club_dao") as dao:
            resp = _client().post(CLUB_URL.format(4, 4))
        assert resp.status_code == 400
        dao.merge_club.assert_not_called()

    @pytest.mark.parametrize(
        ("raised", "status"),
        [
            (_pg_error("MTNF1", "merge_club: club 9 does not exist"), 404),
            (_pg_error("MTBLK", "merge_club: 1 blocker(s), run a dry run to list them"), 409),
            (_pg_error("MTSAM", "merge_club: source and target must be two different clubs"), 400),
            (_pg_error("23505", SECRET.replace("merge_team", "merge_club")), 500),
        ],
    )
    def test_error_mapping_hides_implementation(self, raised, status):
        with patch("app.club_dao") as dao:
            dao.merge_club.side_effect = raised
            resp = _client().post(CLUB_URL.format(3, 4) + "?dry_run=false")
        assert resp.status_code == status
        body = resp.text.lower()
        for leak in ("merge_club", "sqlstate", "teams_pkey", "public.", "constraint"):
            assert leak not in body


@pytest.mark.unit
class TestLogoGapsEndpoint:
    def test_defaults_to_current_season(self):
        with patch("app.club_dao") as club, patch("app.season_dao") as season:
            season.get_current_season_id.return_value = 7
            club.logo_gaps.return_value = {"season_id": 7}
            resp = _client().get("/api/admin/clubs/logo-gaps")
        assert resp.status_code == 200
        club.logo_gaps.assert_called_once_with(7)

    def test_explicit_season(self):
        with patch("app.club_dao") as club, patch("app.season_dao") as season:
            club.logo_gaps.return_value = {"season_id": 3}
            _client().get("/api/admin/clubs/logo-gaps?season_id=3")
        club.logo_gaps.assert_called_once_with(3)
        season.get_current_season_id.assert_not_called()

    def test_season_zero_is_used_not_replaced_by_current(self):
        with patch("app.club_dao") as club, patch("app.season_dao") as season:
            season.get_current_season_id.return_value = 7
            club.logo_gaps.return_value = {"season_id": 0}
            _client().get("/api/admin/clubs/logo-gaps?season_id=0")
        club.logo_gaps.assert_called_once_with(0)
        season.get_current_season_id.assert_not_called()

    def test_all_is_unscoped(self):
        with patch("app.club_dao") as club:
            club.logo_gaps.return_value = {"season_id": None}
            resp = _client().get("/api/admin/clubs/logo-gaps?all=true")
        assert resp.status_code == 200
        club.logo_gaps.assert_called_once_with(None)

    def test_no_current_season_is_400(self):
        with patch("app.club_dao") as club, patch("app.season_dao") as season:
            season.get_current_season_id.return_value = None
            resp = _client().get("/api/admin/clubs/logo-gaps")
        assert resp.status_code == 400
        club.logo_gaps.assert_not_called()

    def test_dao_failure_is_generic_500(self):
        with patch("app.club_dao") as club, patch("app.season_dao") as season:
            season.get_current_season_id.return_value = 7
            club.logo_gaps.side_effect = ValueError("SUPABASE_URL is not configured")
            resp = _client().get("/api/admin/clubs/logo-gaps")
        assert resp.status_code == 500
        assert "SUPABASE_URL" not in resp.text
