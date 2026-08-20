"""Admin access to any team's roster (SB-793).

GET /api/teams/{team_id}/players scopes callers to their own club: it builds
user_club_ids from the caller's club_id, their team's club, and their player
history, then requires the requested team's club to be in that set.

An admin has none of those, so the set comes out empty and every team is
refused — the role meant to see everything could read no roster at all.

SB-792 fixed the frontend picker but its tests mocked fetch, so this endpoint
was never exercised and the bug shipped. These tests exist so the bypass and,
more importantly, the refusal it must not weaken, are both pinned.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

TEAM_IN_OTHER_CLUB = {"id": 19, "name": "IFA", "club_id": 1}
TEAM_DETAILS = {"id": 19, "name": "IFA", "club": {"id": 1, "name": "IFA"}}
ROSTER = [{"id": "p1", "display_name": "A Player", "player_number": 9}]


def _client_as(role, club_id=None, team_id=None):
    """TestClient with the auth dependency overridden to a given caller."""
    from app import app
    from auth import get_current_user_required

    app.dependency_overrides[get_current_user_required] = lambda: {
        "user_id": "u-1",
        "role": role,
        "club_id": club_id,
        "team_id": team_id,
    }
    return TestClient(app)


@pytest.mark.unit
class TestAdminRosterAccess:
    def teardown_method(self):
        from app import app

        app.dependency_overrides.clear()

    def test_admin_reads_a_roster_outside_any_club_they_belong_to(self):
        with (
            patch("app.team_dao") as team_dao,
            patch("app.player_dao") as player_dao,
        ):
            team_dao.get_team_by_id.return_value = TEAM_IN_OTHER_CLUB
            team_dao.get_team_with_details.return_value = TEAM_DETAILS
            player_dao.get_team_players.return_value = ROSTER

            client = _client_as("admin", club_id=None, team_id=None)
            response = client.get("/api/teams/19/players")

            assert response.status_code == 200
            assert response.json()["players"] == ROSTER

    def test_admin_lookup_does_not_query_player_history(self):
        # The history lookup exists to find a club for people who have one.
        # For an admin its result is never consulted, so running it is a
        # wasted query on every roster they open.
        with (
            patch("app.team_dao") as team_dao,
            patch("app.player_dao") as player_dao,
        ):
            team_dao.get_team_by_id.return_value = TEAM_IN_OTHER_CLUB
            team_dao.get_team_with_details.return_value = TEAM_DETAILS
            player_dao.get_team_players.return_value = ROSTER

            client = _client_as("admin")
            client.get("/api/teams/19/players")

            player_dao.get_all_current_player_teams.assert_not_called()

    def test_non_admin_outside_the_club_is_still_refused(self):
        # The behaviour the bypass must not weaken.
        with (
            patch("app.team_dao") as team_dao,
            patch("app.player_dao") as player_dao,
        ):
            team_dao.get_team_by_id.side_effect = lambda tid: (
                TEAM_IN_OTHER_CLUB if tid == 19 else {"id": tid, "club_id": 99}
            )
            player_dao.get_all_current_player_teams.return_value = []

            client = _client_as("team-fan", club_id=99, team_id=None)
            response = client.get("/api/teams/19/players")

            assert response.status_code == 403
            assert "your club" in response.json()["detail"]

    def test_non_admin_inside_the_club_still_passes(self):
        with (
            patch("app.team_dao") as team_dao,
            patch("app.player_dao") as player_dao,
        ):
            team_dao.get_team_by_id.return_value = TEAM_IN_OTHER_CLUB
            team_dao.get_team_with_details.return_value = TEAM_DETAILS
            player_dao.get_team_players.return_value = ROSTER

            client = _client_as("club-fan", club_id=1, team_id=None)
            response = client.get("/api/teams/19/players")

            assert response.status_code == 200

    def test_missing_team_is_still_a_404_for_an_admin(self):
        with patch("app.team_dao") as team_dao:
            team_dao.get_team_by_id.return_value = None

            client = _client_as("admin")
            response = client.get("/api/teams/12345/players")

            assert response.status_code == 404
