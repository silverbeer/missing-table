"""GET /api/me/team-options and PUT /api/me/squad-follows (SB-1543, SB-1608).

A fan follows any squads in their own club for alerts. Choosing squads writes
follows only: it never touches the team a manager assigned (team_id,
assigned_age_group_id), which roster visibility and channel access read.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent / "mt_ai"))
from mt_ai_fakes import (
    ALIASES,
    CLUBS,
    LEAGUES,
    TEAMS,
    U15,
    U16,
    FakeClubs,
    FakeLeagues,
    FakeMatches,
    FakeSeasons,
    FakeTeams,
)

from mt_ai.tools import ToolDeps

DEPS = ToolDeps(
    teams=FakeTeams(TEAMS, ALIASES),
    clubs=FakeClubs(CLUBS),
    leagues=FakeLeagues(LEAGUES),
    matches=FakeMatches(),
    seasons=FakeSeasons(),
)


def _call(method: str, path: str, user: dict, body: dict | None = None, saved: bool = True):
    import app as app_module
    from app import app
    from auth import get_current_user_required

    follows = MagicMock()
    follows.set_club_squads.return_value = saved
    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with (
            patch.object(app_module, "_my_team_deps", lambda: DEPS),
            patch.object(app_module, "_follow_dao", lambda: follows),
            patch.object(app_module.player_dao, "update_user_profile") as update,
        ):
            client = TestClient(app)
            response = client.get(path) if method == "GET" else client.put(path, json=body)
    finally:
        app.dependency_overrides.clear()
    update.assert_not_called()  # choosing squads never rewrites the profile
    return response, follows


def fan(role: str = "club-fan", **profile) -> dict:
    return {"user_id": "u-1", "username": "tom_ifa_fan", "role": role, "club_id": 11, **profile}


CLUB_TEAMS = {102, 109, 111}


@pytest.mark.unit
class TestTeamOptions:
    def test_options_list_the_clubs_squads(self):
        response, _ = _call("GET", "/api/me/team-options", fan())
        assert response.status_code == 200
        body = response.json()
        assert body["club"]["name"] == "IFA"
        assert {(o["team_id"], o["age_group"]["id"]) for o in body["options"]} == {(102, U15), (109, U15), (111, U15)}

    def test_current_is_the_assigned_team(self):
        body = _call("GET", "/api/me/team-options", fan("team-fan", team_id=102, assigned_age_group_id=U15))[0].json()
        assert (body["current_team_id"], body["current_age_group_id"]) == (102, U15)


@pytest.mark.unit
class TestSquadFollows:
    def test_several_squads_are_followed(self):
        body = {"squads": [{"team_id": 102, "age_group_id": U15}, {"team_id": 111, "age_group_id": U15}]}
        response, follows = _call("PUT", "/api/me/squad-follows", fan(), body)
        assert response.status_code == 200
        follows.set_club_squads.assert_called_once_with("u-1", CLUB_TEAMS, {(102, U15), (111, U15)})
        assert response.json()["squads"] == [
            {"team_id": 102, "age_group_id": U15},
            {"team_id": 111, "age_group_id": U15},
        ]

    def test_an_empty_list_unfollows_the_clubs_squads(self):
        response, follows = _call("PUT", "/api/me/squad-follows", fan(), {"squads": []})
        assert response.status_code == 200
        follows.set_club_squads.assert_called_once_with("u-1", CLUB_TEAMS, set())

    def test_a_team_fan_keeps_their_assigned_team(self):
        user = fan("team-fan", team_id=102, assigned_age_group_id=U15)
        response, _ = _call("PUT", "/api/me/squad-follows", user, {"squads": [{"team_id": 111, "age_group_id": U15}]})
        assert response.status_code == 200  # _call asserts the profile was not written

    @pytest.mark.parametrize("team_id,age", [(100, U15), (102, U16), (109, U16)])
    def test_outside_the_club_or_an_age_it_does_not_play_is_400(self, team_id, age):
        body = {"squads": [{"team_id": 102, "age_group_id": U15}, {"team_id": team_id, "age_group_id": age}]}
        response, follows = _call("PUT", "/api/me/squad-follows", fan(), body)
        assert response.status_code == 400
        follows.set_club_squads.assert_not_called()

    def test_a_fan_without_a_club_is_400(self):
        user = {"user_id": "u-1", "role": "club-fan", "club_id": None}
        response, follows = _call("PUT", "/api/me/squad-follows", user, {"squads": []})
        assert response.status_code == 400
        follows.set_club_squads.assert_not_called()

    def test_a_failed_save_is_500(self):
        body = {"squads": [{"team_id": 102, "age_group_id": U15}]}
        response, _ = _call("PUT", "/api/me/squad-follows", fan(), body, saved=False)
        assert response.status_code == 500

    @pytest.mark.parametrize("role", ["club_fan", "team_fan"])
    def test_underscore_fan_spellings_pick_too(self, role):
        response, _ = _call(
            "PUT", "/api/me/squad-follows", fan(role), {"squads": [{"team_id": 102, "age_group_id": U15}]}
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("role", ["team-manager", "team-player", "club_manager", "admin"])
    def test_only_fans_pick(self, role):
        get, _ = _call("GET", "/api/me/team-options", fan(role))
        put, follows = _call("PUT", "/api/me/squad-follows", fan(role), {"squads": []})
        assert get.status_code == 403 and put.status_code == 403
        follows.set_club_squads.assert_not_called()

    def test_the_old_pick_endpoint_is_gone(self):
        response, _ = _call("PUT", "/api/me/team", fan(), {"team_id": 102, "age_group_id": U15})
        assert response.status_code in (404, 405)
