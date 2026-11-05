"""Self-service profile update must not move a user to another team (SB-1542).

`team_id` on the profile is what can_manage_team and can_edit_match read, and the
profile is re-read on every request: a team manager who could PUT their own team_id
could manage any team (its roster of minors, its matches) on the next request.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _user(role: str) -> dict:
    return {"user_id": "u-1", "username": "someone", "role": role, "team_id": 19, "email": None}


@pytest.mark.unit
class TestProfileTeamId:
    def _put(self, role: str, body: dict):
        import app as app_module
        from app import app
        from auth import get_current_user_required

        app.dependency_overrides[get_current_user_required] = lambda: _user(role)
        try:
            with patch.object(app_module.player_dao, "update_user_profile") as update:
                response = TestClient(app).put("/api/auth/profile", json=body)
        finally:
            app.dependency_overrides.clear()
        return response, update

    @pytest.mark.parametrize("role", ["team-manager", "club_manager", "team-player", "team-fan", "club-fan", "user"])
    def test_non_admin_cannot_change_team(self, role):
        response, update = self._put(role, {"team_id": 42})
        assert response.status_code == 403
        update.assert_not_called()

    def test_team_change_rejects_the_whole_update(self):
        # No partial write: a display_name sent alongside team_id is not saved either.
        response, update = self._put("team-manager", {"display_name": "Tom", "team_id": 42})
        assert response.status_code == 403
        update.assert_not_called()

    def test_non_admin_can_still_edit_allowed_fields(self):
        response, update = self._put("team-manager", {"display_name": "Tom"})
        assert response.status_code == 200
        saved = update.call_args.args[1]
        assert saved["display_name"] == "Tom"
        assert "team_id" not in saved

    def test_admin_can_set_team(self):
        response, update = self._put("admin", {"team_id": 42})
        assert response.status_code == 200
        assert update.call_args.args[1]["team_id"] == 42
