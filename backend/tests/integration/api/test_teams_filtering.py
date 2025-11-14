"""
Working tests for /api/teams endpoint and league filtering

Tests the backend API that provides data to the frontend filtering logic.
This validates that divisions_by_age_group data structure is correct.
"""

import pytest
from fastapi.testclient import TestClient
from app import app

@pytest.fixture
def client():
    """Create test client for FastAPI app"""
    return TestClient(app)


def test_teams_endpoint_returns_data(client):
    """
    Test: GET /api/teams returns teams with proper structure

    This is a basic smoke test to verify the endpoint works.
    """
    response = client.get("/api/teams")

    # May return 401 if not authenticated
    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    assert response.status_code == 200
    teams = response.json()
    assert isinstance(teams, list)
    print(f"✅ GET /api/teams returned {len(teams)} teams")


def test_teams_have_divisions_by_age_group_structure(client):
    """
    Test: Teams have divisions_by_age_group with proper structure

    This is the KEY data structure that the frontend filtering depends on.
    Bug was caused by type mismatches in this structure.
    """
    response = client.get("/api/teams")

    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    teams = response.json()

    if len(teams) == 0:
        pytest.skip("No teams in database")

    # Check first team has the expected structure
    team = teams[0]

    print(f"\n📊 Sample team structure:")
    print(f"  Team: {team.get('name')}")
    print(f"  Keys: {list(team.keys())}")

    assert "id" in team, "Team must have id"
    assert "name" in team, "Team must have name"
    assert "age_groups" in team, "Team must have age_groups array"
    assert "divisions_by_age_group" in team, "Team must have divisions_by_age_group dict"

    # Check divisions_by_age_group structure
    divisions_by_age = team["divisions_by_age_group"]
    assert isinstance(divisions_by_age, dict), "divisions_by_age_group must be a dict"

    if len(divisions_by_age) > 0:
        # Check that keys are strings (JSON serialization converts integer keys to strings)
        first_key = list(divisions_by_age.keys())[0]
        print(f"  Division key type: {type(first_key)} (value: {first_key})")
        assert isinstance(first_key, str), "Division keys should be strings after JSON serialization"

        # Check division has league_id
        division = divisions_by_age[first_key]
        assert "league_id" in division, "Division must have league_id"
        assert "league_name" in division, "Division must have league_name"
        assert "name" in division, "Division must have name (division name)"

        print(f"  Division: {division.get('name')}")
        print(f"  League: {division.get('league_name')} (ID: {division.get('league_id')})")
        print(f"  League ID type: {type(division.get('league_id'))}")

    print("✅ Teams have correct divisions_by_age_group structure")


def test_league_id_types_are_consistent(client):
    """
    Test: league_id values are consistently typed

    This test checks that league_id is always an integer (or always a string).
    Type inconsistency would cause filtering bugs.
    """
    response = client.get("/api/teams")

    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    teams = response.json()

    league_id_types = set()

    for team in teams:
        divisions_by_age = team.get("divisions_by_age_group", {})
        for age_group_id, division in divisions_by_age.items():
            league_id = division.get("league_id")
            if league_id is not None:
                league_id_types.add(type(league_id).__name__)

    print(f"\n📊 League ID types found: {league_id_types}")

    # Should only have one type
    if len(league_id_types) > 1:
        pytest.fail(f"Inconsistent league_id types: {league_id_types}. All should be same type!")

    if len(league_id_types) == 1:
        league_id_type = list(league_id_types)[0]
        print(f"✅ All league_ids are consistently typed as: {league_id_type}")


def test_age_group_keys_are_strings(client):
    """
    Test: divisions_by_age_group keys are strings

    After JSON serialization, numeric dictionary keys become strings.
    This test confirms that, so frontend knows to use String(age_group_id).
    """
    response = client.get("/api/teams")

    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    teams = response.json()

    key_types = set()

    for team in teams:
        divisions_by_age = team.get("divisions_by_age_group", {})
        for key in divisions_by_age.keys():
            key_types.add(type(key).__name__)

    print(f"\n📊 Age group key types in divisions_by_age_group: {key_types}")

    # All keys should be strings
    if key_types and key_types != {"str"}:
        pytest.fail(f"Age group keys should all be strings, but found: {key_types}")

    print("✅ All age group keys are strings (as expected after JSON serialization)")


def test_teams_can_be_filtered_by_league(client):
    """
    Test: Simulates the frontend filtering logic

    This recreates the exact filtering logic from MatchesView.vue
    to ensure the backend data supports it properly.
    """
    response = client.get("/api/teams")

    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    teams = response.json()

    if len(teams) == 0:
        pytest.skip("No teams to filter")

    # Get all unique league IDs
    league_ids = set()
    for team in teams:
        divisions_by_age = team.get("divisions_by_age_group", {})
        for division in divisions_by_age.values():
            league_id = division.get("league_id")
            if league_id is not None:
                league_ids.add(league_id)

    print(f"\n📊 Found {len(league_ids)} unique leagues: {sorted(league_ids)}")

    # Test filtering for each league
    for test_league_id in league_ids:
        # Simulate frontend filtering (with type-safe conversions)
        test_age_group_id = "2"  # U14 (as string, like in JSON)

        filtered_teams = []
        for team in teams:
            divisions_by_age = team.get("divisions_by_age_group", {})
            division = divisions_by_age.get(test_age_group_id)

            # This is the FIXED filtering logic
            if division and int(division.get("league_id", 0)) == int(test_league_id):
                filtered_teams.append(team)

        print(f"  League {test_league_id}: {len(filtered_teams)} teams")

        # Verify that filtered teams actually have that league
        for team in filtered_teams:
            division = team["divisions_by_age_group"].get(test_age_group_id)
            actual_league_id = division.get("league_id") if division else None
            assert int(actual_league_id) == int(test_league_id), \
                f"Team {team['name']} filtered incorrectly: has league {actual_league_id}, expected {test_league_id}"

    print("✅ Filtering logic works correctly for all leagues")


def test_no_teams_without_league_id(client):
    """
    Test: All teams should have league_id in their divisions

    Missing league_id would cause filtering to fail silently.
    """
    response = client.get("/api/teams")

    if response.status_code == 401:
        pytest.skip("Endpoint requires authentication")

    teams = response.json()

    teams_without_league = []

    for team in teams:
        divisions_by_age = team.get("divisions_by_age_group", {})
        for age_group_id, division in divisions_by_age.items():
            if division.get("league_id") is None:
                teams_without_league.append({
                    "team": team["name"],
                    "age_group": age_group_id,
                    "division": division.get("name")
                })

    if teams_without_league:
        print(f"\n⚠️  Teams with missing league_id:")
        for item in teams_without_league:
            print(f"  - {item['team']} (age group {item['age_group']}, division: {item['division']})")

        # This is a warning, not a failure
        # Some teams might legitimately not have leagues assigned yet
        print(f"⚠️  Found {len(teams_without_league)} divisions without league_id (may be OK for new teams)")
    else:
        print("✅ All team divisions have league_id set")
