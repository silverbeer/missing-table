"""POST /api/users/me/team-follows (SB-51, SB-1618).

Without age_group_id the whole team is followed — what the mobile apps send.
With it, one squad of any club, and only an age group the team plays.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

USER = {"user_id": "u-1", "username": "fan", "role": "club-fan", "club_id": 11}


def _post(body: dict, plays: bool | None = True, ok: bool = True):
    import api.push as push_module
    from app import app
    from auth import get_current_user_required

    dao = MagicMock()
    dao.follow.return_value = ok
    dao.follow_squad.return_value = ok
    dao.team_plays_age_group.return_value = plays
    app.dependency_overrides[get_current_user_required] = lambda: USER
    try:
        with patch.object(push_module, "_follow_dao", lambda: dao):
            response = TestClient(app).post("/api/users/me/team-follows", json=body)
    finally:
        app.dependency_overrides.clear()
    return response, dao


@pytest.mark.unit
class TestFollowTeam:
    def test_without_age_follows_the_whole_team(self):
        response, dao = _post({"team_id": 7})
        assert response.status_code == 201
        assert response.json() == {"team_id": 7, "age_group_id": None, "following": True}
        dao.follow.assert_called_once_with("u-1", 7)
        dao.follow_squad.assert_not_called()

    def test_with_age_follows_that_squad_of_any_club(self):
        response, dao = _post({"team_id": 7, "age_group_id": 4})
        assert response.status_code == 201
        dao.team_plays_age_group.assert_called_once_with(7, 4)
        dao.follow_squad.assert_called_once_with("u-1", 7, 4)
        dao.follow.assert_not_called()

    def test_an_age_the_team_does_not_play_is_400(self):
        response, dao = _post({"team_id": 7, "age_group_id": 4}, plays=False)
        assert response.status_code == 400
        dao.follow_squad.assert_not_called()

    def test_a_failed_age_check_is_500_not_400(self):
        response, dao = _post({"team_id": 7, "age_group_id": 4}, plays=None)
        assert response.status_code == 500
        dao.follow_squad.assert_not_called()

    def test_a_failed_save_is_500(self):
        response, _ = _post({"team_id": 7, "age_group_id": 4}, ok=False)
        assert response.status_code == 500
