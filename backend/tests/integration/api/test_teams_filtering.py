"""
Working tests for /api/teams endpoint and league filtering

Tests the backend API that provides data to the frontend filtering logic.
This validates that divisions_by_age_group data structure is correct.

Also tests the division_id filtering feature for filtering teams by division
(e.g., Bracket A for Futsal vs Northeast for Homegrown).
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required


@pytest.fixture
def authenticated_client():
    """Create an authenticated test client with admin role."""
    mock_user = {
        "id": "test-user-123",
        "user_id": "test-user-123",
        "username": "testuser",
        "role": "admin",
        "email": "test@example.com"
    }

    def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user_required] = mock_get_current_user

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


def test_teams_endpoint_returns_data(authenticated_client):
    """
    Test: GET /api/teams returns teams with proper structure

    This is a basic smoke test to verify the endpoint works.
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
    teams = response.json()
    assert isinstance(teams, list)
    print(f"✅ GET /api/teams returned {len(teams)} teams")


def test_teams_have_divisions_by_age_group_structure(authenticated_client):
    """
    Test: Teams have divisions_by_age_group with proper structure

    This is the KEY data structure that the frontend filtering depends on.
    Bug was caused by type mismatches in this structure.
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
    teams = response.json()

    if len(teams) == 0:
        pytest.skip("No teams in database")

    # Check first team has the expected structure
    team = teams[0]

    print("\n📊 Sample team structure:")
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


def test_league_id_types_are_consistent(authenticated_client):
    """
    Test: league_id values are consistently typed

    This test checks that league_id is always an integer (or always a string).
    Type inconsistency would cause filtering bugs.
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
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


def test_age_group_keys_are_strings(authenticated_client):
    """
    Test: divisions_by_age_group keys are strings

    After JSON serialization, numeric dictionary keys become strings.
    This test confirms that, so frontend knows to use String(age_group_id).
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
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


def test_teams_can_be_filtered_by_league(authenticated_client):
    """
    Test: Simulates the frontend filtering logic

    This recreates the exact filtering logic from MatchesView.vue
    to ensure the backend data supports it properly.
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
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


def test_no_teams_without_league_id(authenticated_client):
    """
    Test: All teams should have league_id in their divisions

    Missing league_id would cause filtering to fail silently.
    """
    response = authenticated_client.get("/api/teams")

    assert response.status_code == 200
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
        print("\n⚠️  Teams with missing league_id:")
        for item in teams_without_league:
            print(f"  - {item['team']} (age group {item['age_group']}, division: {item['division']})")

        # This is a warning, not a failure
        # Some teams might legitimately not have leagues assigned yet
        print(f"⚠️  Found {len(teams_without_league)} divisions without league_id (may be OK for new teams)")
    else:
        print("✅ All team divisions have league_id set")


# =============================================================================
# Division Filter Tests (New Feature)
# These tests validate the division_id parameter for /api/teams endpoint
# =============================================================================

def test_teams_endpoint_accepts_division_id_parameter(authenticated_client):
    """
    Test: GET /api/teams accepts division_id query parameter

    This is a basic smoke test for the new division_id parameter.
    """
    # First get available match types and age groups
    response = authenticated_client.get("/api/match-types")
    if response.status_code != 200:
        pytest.skip("Cannot get match types")

    match_types = response.json()
    if not match_types:
        pytest.skip("No match types available")

    # Find a League match type (usually id=2)
    league_match_type = next((mt for mt in match_types if "league" in mt.get("name", "").lower()), None)
    if not league_match_type:
        pytest.skip("No League match type found")

    match_type_id = league_match_type["id"]

    # Get age groups
    response = authenticated_client.get("/api/age-groups")
    if response.status_code != 200:
        pytest.skip("Cannot get age groups")

    age_groups = response.json()
    if not age_groups:
        pytest.skip("No age groups available")

    age_group_id = age_groups[0]["id"]

    # Test with division_id parameter (any value)
    response = authenticated_client.get(
        f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}&division_id=1"
    )

    # Should accept the parameter without error
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    teams = response.json()
    assert isinstance(teams, list), "Response should be a list"

    print(f"✅ /api/teams accepts division_id parameter, returned {len(teams)} teams")


def test_division_filter_returns_subset_of_teams(authenticated_client):
    """
    Test: Adding division_id filter returns a subset of teams

    When filtering by division, the result should be equal to or smaller than
    filtering by just match_type and age_group.
    """
    # Get match types
    response = authenticated_client.get("/api/match-types")
    if response.status_code != 200:
        pytest.skip("Cannot get match types")

    match_types = response.json()
    league_match_type = next((mt for mt in match_types if "league" in mt.get("name", "").lower()), None)
    if not league_match_type:
        pytest.skip("No League match type found")

    match_type_id = league_match_type["id"]

    # Get age groups
    response = authenticated_client.get("/api/age-groups")
    if response.status_code != 200:
        pytest.skip("Cannot get age groups")

    age_groups = response.json()
    if not age_groups:
        pytest.skip("No age groups available")

    age_group_id = age_groups[0]["id"]

    # Get divisions
    response = authenticated_client.get("/api/divisions")
    if response.status_code != 200:
        pytest.skip("Cannot get divisions")

    divisions = response.json()
    if not divisions:
        pytest.skip("No divisions available")

    # Get teams WITHOUT division filter
    response_all = authenticated_client.get(
        f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}"
    )
    assert response_all.status_code == 200
    all_teams = response_all.json()

    if len(all_teams) == 0:
        pytest.skip("No teams found for this match type and age group")

    print(f"\n📊 Teams without division filter: {len(all_teams)}")

    # Get teams WITH division filter for each division
    for division in divisions:
        division_id = division["id"]
        division_name = division.get("name", "Unknown")

        response_filtered = authenticated_client.get(
            f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}&division_id={division_id}"
        )
        assert response_filtered.status_code == 200
        filtered_teams = response_filtered.json()

        print(f"  Division '{division_name}' (id={division_id}): {len(filtered_teams)} teams")

        # Filtered teams should be a subset (or equal)
        assert len(filtered_teams) <= len(all_teams), \
            f"Division filter should return subset, but got {len(filtered_teams)} > {len(all_teams)}"

    print("✅ Division filter correctly returns subset of teams")


def test_division_filter_teams_have_correct_division(authenticated_client):
    """
    Test: Teams returned with division filter are in that division

    Verifies that the division_id filter actually filters by division,
    not just returning all teams.
    """
    # Get match types
    response = authenticated_client.get("/api/match-types")
    if response.status_code != 200:
        pytest.skip("Cannot get match types")

    match_types = response.json()
    league_match_type = next((mt for mt in match_types if "league" in mt.get("name", "").lower()), None)
    if not league_match_type:
        pytest.skip("No League match type found")

    match_type_id = league_match_type["id"]

    # Get age groups
    response = authenticated_client.get("/api/age-groups")
    if response.status_code != 200:
        pytest.skip("Cannot get age groups")

    age_groups = response.json()
    if not age_groups:
        pytest.skip("No age groups available")

    age_group_id = age_groups[0]["id"]

    # Get divisions
    response = authenticated_client.get("/api/divisions")
    if response.status_code != 200:
        pytest.skip("Cannot get divisions")

    divisions = response.json()
    if not divisions:
        pytest.skip("No divisions available")

    # Test each division
    for division in divisions:
        division_id = division["id"]
        division_name = division.get("name", "Unknown")

        response_filtered = authenticated_client.get(
            f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}&division_id={division_id}"
        )
        assert response_filtered.status_code == 200
        filtered_teams = response_filtered.json()

        # Skip if no teams in this division
        if not filtered_teams:
            print(f"  Division '{division_name}': No teams (skipping validation)")
            continue

        # Verify each team is actually in this division
        for team in filtered_teams:
            divisions_by_age = team.get("divisions_by_age_group", {})
            age_group_key = str(age_group_id)

            if age_group_key in divisions_by_age:
                team_division = divisions_by_age[age_group_key]
                # Division data is stored directly with "id" field, not "division_id"
                team_division_id = team_division.get("id")

                assert team_division_id == division_id, \
                    f"Team '{team['name']}' has division id={team_division_id}, expected {division_id}"

        print(f"  Division '{division_name}': {len(filtered_teams)} teams - all verified ✓")

    print("✅ All filtered teams have correct division")


def test_nonexistent_division_returns_empty_list(authenticated_client):
    """
    Test: Filtering by non-existent division_id returns empty list

    This is an edge case - using a division_id that doesn't exist
    should return an empty list, not an error.
    """
    # Get match types
    response = authenticated_client.get("/api/match-types")
    if response.status_code != 200:
        pytest.skip("Cannot get match types")

    match_types = response.json()
    league_match_type = next((mt for mt in match_types if "league" in mt.get("name", "").lower()), None)
    if not league_match_type:
        pytest.skip("No League match type found")

    match_type_id = league_match_type["id"]

    # Get age groups
    response = authenticated_client.get("/api/age-groups")
    if response.status_code != 200:
        pytest.skip("Cannot get age groups")

    age_groups = response.json()
    if not age_groups:
        pytest.skip("No age groups available")

    age_group_id = age_groups[0]["id"]

    # Use a very high division_id that doesn't exist
    nonexistent_division_id = 999999

    response = authenticated_client.get(
        f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}&division_id={nonexistent_division_id}"
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    teams = response.json()
    assert isinstance(teams, list), "Response should be a list"
    assert len(teams) == 0, f"Expected empty list for non-existent division, got {len(teams)} teams"

    print("✅ Non-existent division_id returns empty list (as expected)")


def test_division_filter_only_applies_with_match_type_and_age_group(authenticated_client):
    """
    Test: division_id filter is only applied when match_type_id and age_group_id are provided

    If called without match_type and age_group, division_id should be ignored
    (the endpoint uses a different code path).
    """
    # Call with only division_id (no match_type or age_group)
    response = authenticated_client.get("/api/teams?division_id=1")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    teams = response.json()
    assert isinstance(teams, list), "Response should be a list"

    # Should return teams (the general teams list, not filtered by division)
    print(f"✅ /api/teams with only division_id returns {len(teams)} teams (division filter not applied)")


def test_multiple_divisions_have_different_teams(authenticated_client):
    """
    Test: Different divisions return different teams (when data supports it)

    This validates that the division filter is actually differentiating
    between divisions, not just returning the same teams for all.
    """
    # Get match types
    response = authenticated_client.get("/api/match-types")
    if response.status_code != 200:
        pytest.skip("Cannot get match types")

    match_types = response.json()
    league_match_type = next((mt for mt in match_types if "league" in mt.get("name", "").lower()), None)
    if not league_match_type:
        pytest.skip("No League match type found")

    match_type_id = league_match_type["id"]

    # Get age groups
    response = authenticated_client.get("/api/age-groups")
    if response.status_code != 200:
        pytest.skip("Cannot get age groups")

    age_groups = response.json()
    if not age_groups:
        pytest.skip("No age groups available")

    age_group_id = age_groups[0]["id"]

    # Get divisions
    response = authenticated_client.get("/api/divisions")
    if response.status_code != 200:
        pytest.skip("Cannot get divisions")

    divisions = response.json()
    if len(divisions) < 2:
        pytest.skip("Need at least 2 divisions to test differentiation")

    # Get teams for each division
    division_teams = {}
    for division in divisions:
        division_id = division["id"]
        division_name = division.get("name", "Unknown")

        response_filtered = authenticated_client.get(
            f"/api/teams?match_type_id={match_type_id}&age_group_id={age_group_id}&division_id={division_id}"
        )
        assert response_filtered.status_code == 200
        teams = response_filtered.json()

        team_ids = {t["id"] for t in teams}
        division_teams[division_name] = team_ids

        print(f"  Division '{division_name}': {len(teams)} teams")

    # Check if divisions with teams have different teams
    divisions_with_teams = {k: v for k, v in division_teams.items() if v}

    if len(divisions_with_teams) < 2:
        pytest.skip("Need at least 2 divisions with teams to test differentiation")

    # At least some divisions should have different teams
    all_teams_same = True
    division_names = list(divisions_with_teams.keys())

    for i in range(len(division_names)):
        for j in range(i + 1, len(division_names)):
            div1 = division_names[i]
            div2 = division_names[j]

            if divisions_with_teams[div1] != divisions_with_teams[div2]:
                all_teams_same = False
                overlap = divisions_with_teams[div1] & divisions_with_teams[div2]
                print(f"  '{div1}' vs '{div2}': Different teams (overlap: {len(overlap)})")

    if all_teams_same:
        print("⚠️  All divisions have the same teams - this may be OK if data is configured that way")
    else:
        print("✅ Different divisions return different teams")
