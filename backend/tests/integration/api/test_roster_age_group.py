"""
Integration tests for the bulk age-group assignment endpoint (SB-69).

PATCH /api/teams/{team_id}/players/age-group bulk-assigns players.age_group_id
on existing roster rows so the live-match lineup (which filters strictly on
age_group_id since SB-68) is no longer empty for pre-existing rosters.

These cover the endpoint contract — authz, validation, and not-found — without
depending on specific seeded player rows. The happy-path mutation is exercised
by the frontend component spec and manual verification.
"""

import pytest
from fastapi.testclient import TestClient

ENDPOINT = "/api/teams/{team_id}/players/age-group"
VALID_BODY = {"season_id": 1, "player_ids": [1], "age_group_id": 1}


class TestBulkAssignAgeGroup:
    """Contract tests for PATCH /api/teams/{team_id}/players/age-group."""

    @pytest.mark.e2e
    def test_requires_manager_or_admin_role(self, authenticated_client: TestClient):
        """A plain 'user' role is rejected with 403 before any DB work."""
        response = authenticated_client.patch(
            ENDPOINT.format(team_id=1), json=VALID_BODY
        )
        assert response.status_code == 403

    @pytest.mark.e2e
    def test_empty_player_ids_is_422(self, admin_client: TestClient):
        """player_ids must be non-empty (Pydantic min_length=1)."""
        body = {"season_id": 1, "player_ids": [], "age_group_id": 1}
        response = admin_client.patch(ENDPOINT.format(team_id=1), json=body)
        assert response.status_code == 422

    @pytest.mark.e2e
    def test_unknown_team_is_404(self, admin_client: TestClient):
        """A non-existent team returns 404."""
        response = admin_client.patch(
            ENDPOINT.format(team_id=99_999_999), json=VALID_BODY
        )
        assert response.status_code == 404

    @pytest.mark.e2e
    def test_invalid_age_group_is_400(self, admin_client: TestClient):
        """A real team with a bogus age_group_id returns a clean 400."""
        teams = admin_client.get("/api/teams").json()
        if not teams:
            pytest.skip("No teams seeded in test database")
        team_id = teams[0]["id"]
        body = {"season_id": 1, "player_ids": [1], "age_group_id": 999_999}
        response = admin_client.patch(ENDPOINT.format(team_id=team_id), json=body)
        assert response.status_code == 400
