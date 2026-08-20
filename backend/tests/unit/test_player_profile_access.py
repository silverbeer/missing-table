"""Who may view a player's profile (SB-797).

GET /api/player-profile/{user_id} resolved the viewer's clubs from
player_team_history alone. Almost nobody is in that table — 32 of 33 accounts
have no rows — so the club intersection was empty and the endpoint refused
every club manager, every fan and every admin. Only self-views and the single
account with history worked.

Same shape as SB-793: authorization built on one source of affiliation, which
most real accounts do not have.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

TARGET_ID = "player-1"
# Target plays for a team in club 1.
TARGET_TEAMS = [{"team": {"id": 19, "name": "IFA", "club": {"id": 1, "name": "IFA"}}}]
TARGET_PROFILE = {"id": TARGET_ID, "display_name": "A Player", "team_id": 19}


def _client(viewer):
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: viewer
    return TestClient(app)


def _viewer(role, user_id="viewer-1", club_id=None, team_id=None):
    return {"user_id": user_id, "username": role, "role": role, "club_id": club_id, "team_id": team_id}


@pytest.mark.unit
class TestPlayerProfileAccess:
    def teardown_method(self):
        from app import app

        app.dependency_overrides.clear()

    def _patched(self, viewer_history=None):
        """player_dao/team_dao doubles. viewer_history defaults to none, which
        is the real-world case for all but one account."""
        player_dao = MagicMock()
        player_dao.get_user_profile_with_relationships.return_value = TARGET_PROFILE

        def current_teams(uid):
            if uid == TARGET_ID:
                return TARGET_TEAMS
            return viewer_history or []

        player_dao.get_all_current_player_teams.side_effect = current_teams
        team_dao = MagicMock()
        team_dao.get_team_by_id.return_value = {"id": 19, "club_id": 1}
        return player_dao, team_dao

    def _get(self, viewer, player_dao, team_dao):
        with (
            patch("app.player_dao", player_dao),
            patch("app.team_dao", team_dao),
            patch("app.match_dao", MagicMock()),
        ):
            return _client(viewer).get(f"/api/players/{TARGET_ID}/profile")

    def test_admin_can_view_any_profile(self):
        player_dao, team_dao = self._patched()
        response = self._get(_viewer("admin"), player_dao, team_dao)

        assert response.status_code == 200

    def test_club_manager_of_the_same_club_can_view(self):
        # Carries club_id and no history — refused before this fix.
        player_dao, team_dao = self._patched()
        response = self._get(_viewer("club_manager", club_id=1), player_dao, team_dao)

        assert response.status_code == 200

    def test_club_fan_of_the_same_club_can_view(self):
        player_dao, team_dao = self._patched()
        response = self._get(_viewer("club-fan", club_id=1), player_dao, team_dao)

        assert response.status_code == 200

    def test_team_manager_resolves_their_club_through_their_team(self):
        # Carries team_id only; the club comes from the team.
        player_dao, team_dao = self._patched()
        response = self._get(_viewer("team-manager", team_id=19), player_dao, team_dao)

        assert response.status_code == 200

    def test_player_with_history_still_resolves(self):
        # The one path that already worked must keep working.
        player_dao, team_dao = self._patched(viewer_history=TARGET_TEAMS)
        response = self._get(_viewer("team-player"), player_dao, team_dao)

        assert response.status_code == 200

    def test_someone_in_a_different_club_is_still_refused(self):
        # The refusal this must not weaken.
        player_dao, team_dao = self._patched()
        team_dao.get_team_by_id.return_value = {"id": 77, "club_id": 99}
        response = self._get(_viewer("club-fan", club_id=99), player_dao, team_dao)

        assert response.status_code == 403
        assert "your club" in response.json()["detail"]

    def test_a_viewer_with_no_affiliation_at_all_is_refused(self):
        player_dao, team_dao = self._patched()
        response = self._get(_viewer("team-fan"), player_dao, team_dao)

        assert response.status_code == 403

    def test_viewing_your_own_profile_needs_no_club(self):
        player_dao, team_dao = self._patched()
        viewer = _viewer("team-fan", user_id=TARGET_ID)
        response = self._get(viewer, player_dao, team_dao)

        assert response.status_code == 200

    def test_unknown_player_is_404(self):
        player_dao, team_dao = self._patched()
        player_dao.get_user_profile_with_relationships.return_value = None
        response = self._get(_viewer("admin"), player_dao, team_dao)

        assert response.status_code == 404
