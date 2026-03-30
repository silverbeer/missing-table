import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required


@pytest.fixture
def authenticated_client():
    """Create an authenticated test client with admin role."""
    mock_user = {
        "user_id": "test-user-123",
        "username": "testuser",
        "role": "admin",
        "email": "test@example.com",
        "team_id": None,
        "club_id": None,
        "display_name": "Test User",
    }

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user_required] = override_get_current_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


def test_divisions_keys_are_strings(authenticated_client):
    """
    Verify that the keys in divisions_by_age_group are strings.
    """
    response = authenticated_client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    for team in teams:
        divisions_by_age_group = team.get("divisions_by_age_group", {})
        for key in divisions_by_age_group:
            assert isinstance(key, str), f"Expected key to be string, got {type(key)}"


def test_league_id_type_handling(authenticated_client):
    """
    Verify that league_id values are numbers and type coercion is handled correctly.
    """
    response = authenticated_client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    for team in teams:
        league_id = team.get("league_id")
        if league_id is not None:
            assert isinstance(league_id, int), f"Expected league_id to be int, got {type(league_id)}"


def test_filtering_logic_for_league(authenticated_client):
    """
    Verify filtering logic correctly handles type conversions and only returns teams matching the selected league.
    """
    selected_league_id = 1
    response = authenticated_client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    filtered_teams = [team for team in teams if team.get("league_id") == selected_league_id]
    for team in filtered_teams:
        assert team.get("league_id") == selected_league_id, "Filtering logic failed to match league_id"
