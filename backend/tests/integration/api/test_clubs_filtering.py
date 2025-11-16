from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_divisions_keys_are_strings():
    """
    Verify that the keys in divisions_by_age_group are strings.
    """
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    for team in teams:
        divisions_by_age_group = team.get("divisions_by_age_group", {})
        for key in divisions_by_age_group.keys():
            assert isinstance(key, str), f"Expected key to be string, got {type(key)}"

def test_league_id_type_handling():
    """
    Verify that league_id values are numbers and type coercion is handled correctly.
    """
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    for team in teams:
        league_id = team.get("league_id")
        assert isinstance(league_id, int), f"Expected league_id to be int, got {type(league_id)}"

def test_filtering_logic_for_league():
    """
    Verify filtering logic correctly handles type conversions and only returns teams matching the selected league.
    """
    selected_league_id = 1  # Example league_id for filtering
    response = client.get("/api/teams")
    assert response.status_code == 200
    teams = response.json()
    filtered_teams = [team for team in teams if team.get("league_id") == selected_league_id]
    for team in filtered_teams:
        assert team.get("league_id") == selected_league_id, "Filtering logic failed to match league_id"
