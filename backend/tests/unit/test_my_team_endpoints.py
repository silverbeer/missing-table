"""PUT/GET /api/me/team*: a fan picks "my team" (SB-1543).

The pick writes team_id, which roster visibility reads (via its club): only a team
in the fan's own club, at an age group it plays, is accepted.
"""

import sys
from pathlib import Path
from unittest.mock import patch

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


def _call(method: str, path: str, user: dict, body: dict | None = None):
    import app as app_module
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: user
    try:
        with (
            patch.object(app_module, "_my_team_deps", lambda: DEPS),
            patch.object(app_module.player_dao, "update_user_profile") as update,
        ):
            client = TestClient(app)
            response = client.get(path) if method == "GET" else client.put(path, json=body)
    finally:
        app.dependency_overrides.clear()
    return response, update


def fan(role: str = "club-fan", **profile) -> dict:
    return {"user_id": "u-1", "username": "tom_ifa_fan", "role": role, "club_id": 11, **profile}


@pytest.mark.unit
class TestMyTeamEndpoints:
    def test_options_list_the_clubs_squads(self):
        response, _ = _call("GET", "/api/me/team-options", fan())
        assert response.status_code == 200
        body = response.json()
        assert body["club"]["name"] == "IFA"
        assert {(o["team_id"], o["age_group"]["id"]) for o in body["options"]} == {(102, U15), (109, U15), (111, U15)}

    def test_a_valid_pick_saves_team_and_age(self):
        response, update = _call("PUT", "/api/me/team", fan(), {"team_id": 102, "age_group_id": U15})
        assert response.status_code == 200
        saved = update.call_args.args[1]
        assert (saved["team_id"], saved["assigned_age_group_id"]) == (102, U15)

    def test_a_team_fan_can_repick_within_the_club(self):
        response, _ = _call("PUT", "/api/me/team", fan("team-fan", team_id=102), {"team_id": 111, "age_group_id": U15})
        assert response.status_code == 200

    @pytest.mark.parametrize("team_id,age", [(100, U15), (102, U16), (109, U16)])
    def test_outside_the_club_or_an_age_it_does_not_play_is_400(self, team_id, age):
        response, update = _call("PUT", "/api/me/team", fan(), {"team_id": team_id, "age_group_id": age})
        assert response.status_code == 400
        update.assert_not_called()

    def test_half_a_pick_is_400(self):
        response, update = _call("PUT", "/api/me/team", fan(), {"team_id": 102})
        assert response.status_code == 400
        update.assert_not_called()

    def test_clearing_drops_team_and_age(self):
        response, update = _call("PUT", "/api/me/team", fan(team_id=102, assigned_age_group_id=U15), {})
        assert response.status_code == 200
        saved = update.call_args.args[1]
        assert saved["team_id"] is None and saved["assigned_age_group_id"] is None

    def test_clearing_keeps_a_clubless_team_fans_team(self):
        user = {"user_id": "u-1", "role": "team-fan", "team_id": 102, "club_id": None, "assigned_age_group_id": U15}
        _, update = _call("PUT", "/api/me/team", user, {})
        saved = update.call_args.args[1]
        assert "team_id" not in saved and saved["assigned_age_group_id"] is None

    @pytest.mark.parametrize("role", ["club_fan", "team_fan"])
    def test_underscore_fan_spellings_pick_too(self, role):
        response, _ = _call("PUT", "/api/me/team", fan(role), {"team_id": 102, "age_group_id": U15})
        assert response.status_code == 200

    @pytest.mark.parametrize("role", ["team-manager", "team-player", "club_manager", "admin"])
    def test_only_fans_pick(self, role):
        get, _ = _call("GET", "/api/me/team-options", fan(role))
        put, update = _call("PUT", "/api/me/team", fan(role), {"team_id": 102, "age_group_id": U15})
        assert get.status_code == 403 and put.status_code == 403
        update.assert_not_called()
