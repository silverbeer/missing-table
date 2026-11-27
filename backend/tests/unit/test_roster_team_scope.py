"""Manager endpoints are scoped to the teams the caller manages (SB-1802).

`require_team_manager_or_admin` checks the role only. These tests pin the
second check — *which* team — on every write that takes a team or player from
the caller, and that a denial happens before any DAO write.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

OWN_TEAM, OTHER_TEAM = 1, 2
OWN_CLUB, OTHER_CLUB = 10, 20
TEAM_CLUBS = {OWN_TEAM: OWN_CLUB, OTHER_TEAM: OTHER_CLUB}
PLAYER_ID = "player-uuid"

USERS = {
    "admin": {"role": "admin", "user_id": "u-admin", "username": "admin"},
    "team manager": {"role": "team-manager", "team_id": OWN_TEAM, "user_id": "u-tm", "username": "tm"},
    "club manager": {"role": "club_manager", "club_id": OWN_CLUB, "user_id": "u-cm", "username": "cm"},
    "club manager, no club": {"role": "club_manager", "club_id": None, "user_id": "u-cm0", "username": "cm0"},
}

# (user, team, allowed) — the matrix every team-scoped endpoint must satisfy
MATRIX = [
    ("admin", OWN_TEAM, True),
    ("admin", OTHER_TEAM, True),
    ("team manager", OWN_TEAM, True),
    ("team manager", OTHER_TEAM, False),
    ("club manager", OWN_TEAM, True),
    ("club manager", OTHER_TEAM, False),
    ("club manager, no club", OWN_TEAM, False),
]


@contextmanager
def _client(user: dict):
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: user
    with (
        patch("app.auth_manager._get_team_club_id", side_effect=TEAM_CLUBS.get),
        patch("app.team_dao") as team_dao,
        patch("app.roster_dao") as roster_dao,
        patch("app.player_dao") as player_dao,
        patch("app.season_dao") as season_dao,
    ):
        mocks = MagicMock(team_dao=team_dao, roster_dao=roster_dao, player_dao=player_dao, season_dao=season_dao)
        team_dao.get_team_by_id.side_effect = lambda tid: {"id": tid, "club_id": TEAM_CLUBS.get(tid)}
        season_dao.get_all_age_groups.return_value = [{"id": 5}]
        roster_dao.get_player_by_jersey.return_value = None
        roster_dao.get_team_roster.return_value = []
        try:
            yield TestClient(app), mocks
        finally:
            app.dependency_overrides.clear()


def _roster_player(team_id: int) -> dict:
    return {"id": 7, "team_id": team_id, "season_id": 1, "age_group_id": 5, "jersey_number": 9}


# name -> (method, path template, json body, query, DAO write attribute on roster_dao/team_dao)
ROSTER_ENDPOINTS = {
    "create": (
        "post",
        "/api/teams/{t}/roster",
        {"season_id": 1, "jersey_number": 9, "first_name": "A"},
        None,
        ("roster_dao", "create_player"),
    ),
    "bulk create": (
        "post",
        "/api/teams/{t}/roster/bulk",
        {"season_id": 1, "players": [{"jersey_number": 9, "first_name": "A"}]},
        None,
        ("roster_dao", "bulk_create_players"),
    ),
    "assign age group": (
        "patch",
        "/api/teams/{t}/players/age-group",
        {"season_id": 1, "player_ids": [7], "age_group_id": 5},
        None,
        ("roster_dao", "bulk_update_age_group"),
    ),
    "update": (
        "put",
        "/api/teams/{t}/roster/7",
        {"first_name": "B"},
        None,
        ("roster_dao", "update_player"),
    ),
    "jersey number": (
        "put",
        "/api/teams/{t}/roster/7/number",
        {"new_number": 10},
        None,
        ("roster_dao", "update_jersey_number"),
    ),
    "renumber": (
        "post",
        "/api/teams/{t}/roster/renumber",
        {"changes": [{"player_id": 7, "new_number": 10}]},
        {"season_id": 1},
        ("roster_dao", "bulk_renumber"),
    ),
    "delete": (
        "delete",
        "/api/teams/{t}/roster/7",
        None,
        None,
        ("roster_dao", "delete_player"),
    ),
}


@pytest.mark.unit
class TestRosterEndpointsScope:
    @pytest.mark.parametrize("endpoint", list(ROSTER_ENDPOINTS))
    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_matrix(self, endpoint, who, team_id, allowed):
        method, path, body, params, (dao_name, write) = ROSTER_ENDPOINTS[endpoint]
        with _client(USERS[who]) as (client, mocks):
            roster_dao = mocks.roster_dao
            roster_dao.get_player_by_id.return_value = _roster_player(team_id)
            roster_dao.create_player.return_value = {"id": 7}
            roster_dao.bulk_create_players.return_value = [{"id": 7}]
            roster_dao.bulk_update_age_group.return_value = [{"id": 7}]
            roster_dao.update_player.return_value = {"id": 7}
            roster_dao.update_jersey_number.return_value = {"id": 7}
            roster_dao.bulk_renumber.return_value = True
            roster_dao.delete_player.return_value = True

            kwargs = {"params": params}
            if body is not None:
                kwargs["json"] = body
            response = client.request(method.upper(), path.format(t=team_id), **kwargs)

            write_mock = getattr(getattr(mocks, dao_name), write)
            if allowed:
                assert response.status_code == 200, response.text
                write_mock.assert_called_once()
            else:
                assert response.status_code == 403
                assert response.json()["detail"] == "You can only manage your own team"
                write_mock.assert_not_called()

    def test_player_not_on_team_still_404(self):
        """The team check does not replace the player-belongs-to-team check."""
        with _client(USERS["team manager"]) as (client, mocks):
            mocks.roster_dao.get_player_by_id.return_value = _roster_player(OTHER_TEAM)

            response = client.delete(f"/api/teams/{OWN_TEAM}/roster/7")

            assert response.status_code == 404
            mocks.roster_dao.delete_player.assert_not_called()


@pytest.mark.unit
class TestTeamMappingScope:
    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_create(self, who, team_id, allowed):
        with _client(USERS[who]) as (client, mocks):
            mocks.team_dao.create_team_mapping.return_value = {"team_id": team_id}

            response = client.post("/api/team-mappings", json={"team_id": team_id, "age_group_id": 5, "division_id": 3})

            assert response.status_code == (200 if allowed else 403)
            assert mocks.team_dao.create_team_mapping.called is allowed

    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_delete(self, who, team_id, allowed):
        with _client(USERS[who]) as (client, mocks):
            mocks.team_dao.delete_team_mapping.return_value = True

            response = client.delete(f"/api/team-mappings/{team_id}/5/3")

            assert response.status_code == (200 if allowed else 403)
            assert mocks.team_dao.delete_team_mapping.called is allowed


@pytest.mark.unit
class TestAdminPlayerScope:
    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_update_player(self, who, team_id, allowed):
        with _client(USERS[who]) as (client, mocks):
            mocks.player_dao.get_all_current_player_teams.return_value = [{"team_id": team_id}]
            mocks.player_dao.update_player_admin.return_value = {"id": PLAYER_ID}

            response = client.put(f"/api/admin/players/{PLAYER_ID}", json={"display_name": "X"})

            assert response.status_code == (200 if allowed else 403)
            assert mocks.player_dao.update_player_admin.called is allowed

    @pytest.mark.parametrize("who,allowed", [("admin", True), ("team manager", False), ("club manager", False)])
    def test_update_player_on_no_team_is_admin_only(self, who, allowed):
        with _client(USERS[who]) as (client, mocks):
            mocks.player_dao.get_all_current_player_teams.return_value = []
            mocks.player_dao.update_player_admin.return_value = {"id": PLAYER_ID}

            response = client.put(f"/api/admin/players/{PLAYER_ID}", json={"display_name": "X"})

            assert response.status_code == (200 if allowed else 403)
            assert mocks.player_dao.update_player_admin.called is allowed

    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_assign_to_target_team(self, who, team_id, allowed):
        """An unattached player can be assigned to any team the caller manages."""
        with _client(USERS[who]) as (client, mocks):
            mocks.player_dao.get_all_current_player_teams.return_value = []
            mocks.player_dao.create_player_history_entry.return_value = {"id": 1}

            response = client.post(f"/api/admin/players/{PLAYER_ID}/teams", json={"team_id": team_id, "season_id": 1})

            assert response.status_code == (200 if allowed else 403)
            assert mocks.player_dao.create_player_history_entry.called is allowed

    @pytest.mark.parametrize("who,allowed", [("admin", True), ("team manager", False), ("club manager", False)])
    def test_cannot_take_another_teams_player(self, who, allowed):
        """Managing the target team is not enough when the player is on someone else's team."""
        with _client(USERS[who]) as (client, mocks):
            mocks.player_dao.get_all_current_player_teams.return_value = [{"team_id": OTHER_TEAM}]
            mocks.player_dao.create_player_history_entry.return_value = {"id": 1}

            response = client.post(f"/api/admin/players/{PLAYER_ID}/teams", json={"team_id": OWN_TEAM, "season_id": 1})

            assert response.status_code == (200 if allowed else 403)
            assert mocks.player_dao.create_player_history_entry.called is allowed
            assert mocks.roster_dao.create_player.called is False

    @pytest.mark.parametrize("who,team_id,allowed", MATRIX)
    def test_end_assignment(self, who, team_id, allowed):
        with _client(USERS[who]) as (client, mocks):
            mocks.player_dao.get_player_history_entry_by_id.return_value = {"id": 3, "team_id": team_id}
            mocks.player_dao.end_player_team_assignment.return_value = {"id": 3}

            response = client.put("/api/admin/players/teams/3/end")

            assert response.status_code == (200 if allowed else 403)
            assert mocks.player_dao.end_player_team_assignment.called is allowed

    def test_end_missing_assignment_is_404(self):
        with _client(USERS["team manager"]) as (client, mocks):
            mocks.player_dao.get_player_history_entry_by_id.return_value = None

            response = client.put("/api/admin/players/teams/3/end")

            assert response.status_code == 404
            mocks.player_dao.end_player_team_assignment.assert_not_called()


@pytest.mark.unit
class TestDeleteMatchScope:
    @pytest.mark.parametrize("who,allowed", [("admin", True), ("team manager", False), ("club manager", False)])
    def test_other_teams_match(self, who, allowed):
        """Denial is a 403, not swallowed into a 500, and nothing is deleted."""
        with _client(USERS[who]) as (client, _), patch("app.match_dao") as match_dao:
            match_dao.get_match_by_id.return_value = {
                "id": 50,
                "home_team_id": OTHER_TEAM,
                "away_team_id": OTHER_TEAM,
                "photo_key": None,
            }
            match_dao.delete_match.return_value = True

            response = client.delete("/api/matches/50")

            assert response.status_code == (200 if allowed else 403)
            assert match_dao.delete_match.called is allowed
