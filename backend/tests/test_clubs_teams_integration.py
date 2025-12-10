"""
Integration test for clubs and teams CRUD operations.
Tests the basic workflow of creating a club and linking teams to it.
"""
import pytest
from fastapi.testclient import TestClient
import os
from dotenv import load_dotenv

from app import app

# Load environment
os.environ['APP_ENV'] = 'local'
load_dotenv('.env.local')

# Test client
client = TestClient(app)


class TestClubsTeamsIntegration:
    """Test the basic club -> team relationship workflow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin and prepare for cleanup."""
        # Login to get auth token
        login_response = client.post(
            "/api/auth/login",
            json={"username": "tom", "password": "admin123"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"

        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Track created resources for cleanup
        self.created_club_id = None
        self.created_team_ids = []

        yield

        # Cleanup: delete created resources
        for team_id in self.created_team_ids:
            try:
                client.delete(f"/api/teams/{team_id}", headers=self.headers)
            except Exception:
                pass  # Ignore cleanup errors

        if self.created_club_id:
            try:
                client.delete(f"/api/clubs/{self.created_club_id}", headers=self.headers)
            except Exception:
                pass  # Ignore cleanup errors

    def test_create_club_and_link_team(self):
        """
        Test the basic workflow:
        1. Create a club
        2. Create a team
        3. Link the team to the club (set parent_club_id)
        4. Verify the relationship
        """
        # Step 1: Create a club
        print("\n=== Step 1: Creating club ===")
        club_data = {
            "name": "Test Integration Club",
            "city": "Boston, MA",
            "website": "https://testclub.com",
            "description": "A test club for integration testing"
        }

        club_response = client.post(
            "/api/clubs",
            json=club_data,
            headers=self.headers
        )

        print(f"Club creation status: {club_response.status_code}")
        print(f"Club creation response: {club_response.text}")

        assert club_response.status_code == 200, f"Failed to create club: {club_response.text}"

        club = club_response.json()
        self.created_club_id = club["id"]

        print(f"✅ Club created with ID: {self.created_club_id}")
        assert club["name"] == club_data["name"]
        assert club["city"] == club_data["city"]

        # Step 2: Get or create division and age group
        print("\n=== Step 2: Getting reference data ===")

        # Get divisions, create one if none exist
        divisions_response = client.get("/api/divisions", headers=self.headers)
        assert divisions_response.status_code == 200
        divisions = divisions_response.json()

        if len(divisions) == 0:
            print("No divisions found, creating test division...")
            # Get leagues first, create one if none exist
            leagues_response = client.get("/api/leagues", headers=self.headers)
            assert leagues_response.status_code == 200
            leagues = leagues_response.json()

            if len(leagues) == 0:
                league_response = client.post(
                    "/api/leagues",
                    json={"name": "Test League", "description": "Test"},
                    headers=self.headers
                )
                assert league_response.status_code == 200
                league_id = league_response.json()["id"]
            else:
                league_id = leagues[0]["id"]

            # Create division
            division_response = client.post(
                "/api/divisions",
                json={"name": "Test Division", "league_id": league_id},
                headers=self.headers
            )
            assert division_response.status_code == 200
            division_id = division_response.json()["id"]
        else:
            division_id = divisions[0]["id"]

        print(f"Using division ID: {division_id}")

        # Get age groups, create one if none exist
        age_groups_response = client.get("/api/age-groups", headers=self.headers)
        assert age_groups_response.status_code == 200
        age_groups = age_groups_response.json()

        if len(age_groups) == 0:
            print("No age groups found, creating test age group...")
            age_group_response = client.post(
                "/api/age-groups",
                json={"name": "U13"},
                headers=self.headers
            )
            assert age_group_response.status_code == 200
            age_group_id = age_group_response.json()["id"]
        else:
            age_group_id = age_groups[0]["id"]

        print(f"Using age group ID: {age_group_id}")

        # Step 3: Create a team with required fields
        print("\n=== Step 3: Creating team ===")
        team_data = {
            "name": "Test Integration Team",
            "city": "Boston, MA",
            "age_group_ids": [age_group_id],
            "division_id": division_id,
            "academy_team": False
        }

        team_response = client.post(
            "/api/teams",
            json=team_data,
            headers=self.headers
        )

        print(f"Team creation status: {team_response.status_code}")
        print(f"Team creation response: {team_response.text}")

        assert team_response.status_code == 200, f"Failed to create team: {team_response.text}"

        team = team_response.json()
        # The response might be a message dict, check if it has an id or if we need to fetch it
        if "message" in team:
            # Need to fetch the team to get its ID
            teams_response = client.get("/api/teams", headers=self.headers)
            assert teams_response.status_code == 200
            teams = teams_response.json()
            team = next((t for t in teams if t["name"] == team_data["name"]), None)
            assert team is not None, "Could not find created team"

        team_id = team["id"]
        self.created_team_ids.append(team_id)

        print(f"✅ Team created with ID: {team_id}")
        print(f"   Initial parent_club_id: {team.get('parent_club_id')}")

        # Step 4: Link team to club (update parent_club_id)
        print("\n=== Step 4: Linking team to club ===")
        update_data = {
            "name": team_data["name"],
            "city": team_data["city"],
            "academy_team": team_data["academy_team"],
            "parent_club_id": self.created_club_id
        }

        print(f"Update payload: {update_data}")

        update_response = client.put(
            f"/api/teams/{team_id}",
            json=update_data,
            headers=self.headers
        )

        print(f"Update status: {update_response.status_code}")
        print(f"Update response: {update_response.text}")

        assert update_response.status_code == 200, f"Failed to update team: {update_response.text}"

        updated_team = update_response.json()
        print(f"Updated team parent_club_id: {updated_team.get('parent_club_id')}")

        # Step 5: Verify the relationship
        print("\n=== Step 5: Verifying relationship ===")

        # Fetch the team again to confirm parent_club_id is set
        team_fetch_response = client.get("/api/teams", headers=self.headers)
        assert team_fetch_response.status_code == 200
        teams = team_fetch_response.json()
        fetched_team = next((t for t in teams if t["id"] == team_id), None)

        assert fetched_team is not None, "Could not find team after update"
        print(f"Fetched team parent_club_id: {fetched_team.get('parent_club_id')}")

        # THE KEY ASSERTION: parent_club_id should be set
        assert fetched_team.get("parent_club_id") == self.created_club_id, \
            f"Expected parent_club_id={self.created_club_id}, got {fetched_team.get('parent_club_id')}"

        print(f"✅ Team successfully linked to club!")

        # Fetch club with teams to verify it shows up
        print("\n=== Step 6: Verifying club shows team ===")
        club_fetch_response = client.get("/api/clubs", headers=self.headers)
        assert club_fetch_response.status_code == 200
        clubs = club_fetch_response.json()
        fetched_club = next((c for c in clubs if c["id"] == self.created_club_id), None)

        assert fetched_club is not None, "Could not find club"
        print(f"Club team count: {fetched_club.get('team_count', 0)}")
        print(f"Club teams: {[t['name'] for t in fetched_club.get('teams', [])]}")

        assert fetched_club.get("team_count", 0) >= 1, \
            f"Expected club to have at least 1 team, got {fetched_club.get('team_count', 0)}"

        team_names = [t["name"] for t in fetched_club.get("teams", [])]
        assert "Test Integration Team" in team_names, \
            f"Expected to find 'Test Integration Team' in club teams, got {team_names}"

        print("✅ All tests passed!")

    def test_create_team_with_parent_club(self):
        """
        Test creating a team with parent_club_id set during creation.
        This tests the new functionality where parent_club_id is supported in team creation.
        """
        # Step 1: Create a club
        print("\n=== Step 1: Creating club ===")
        club_data = {
            "name": "Test Parent Club",
            "city": "New York, NY",
            "website": "https://parentclub.com",
            "description": "A test club for parent_club_id testing"
        }

        club_response = client.post(
            "/api/clubs",
            json=club_data,
            headers=self.headers
        )

        assert club_response.status_code == 200, f"Failed to create club: {club_response.text}"
        club = club_response.json()
        self.created_club_id = club["id"]
        print(f"✅ Club created with ID: {self.created_club_id}")

        # Step 2: Get or create division and age group
        print("\n=== Step 2: Getting reference data ===")

        # Get divisions, create one if none exist
        divisions_response = client.get("/api/divisions", headers=self.headers)
        assert divisions_response.status_code == 200
        divisions = divisions_response.json()

        if len(divisions) == 0:
            print("No divisions found, creating test division...")
            # Get leagues first, create one if none exist
            leagues_response = client.get("/api/leagues", headers=self.headers)
            assert leagues_response.status_code == 200
            leagues = leagues_response.json()

            if len(leagues) == 0:
                league_response = client.post(
                    "/api/leagues",
                    json={"name": "Test League", "description": "Test"},
                    headers=self.headers
                )
                assert league_response.status_code == 200
                league_id = league_response.json()["id"]
            else:
                league_id = leagues[0]["id"]

            # Create division
            division_response = client.post(
                "/api/divisions",
                json={"name": "Test Division", "league_id": league_id},
                headers=self.headers
            )
            assert division_response.status_code == 200
            division_id = division_response.json()["id"]
        else:
            division_id = divisions[0]["id"]

        print(f"Using division ID: {division_id}")

        # Get age groups, create one if none exist
        age_groups_response = client.get("/api/age-groups", headers=self.headers)
        assert age_groups_response.status_code == 200
        age_groups = age_groups_response.json()

        if len(age_groups) == 0:
            print("No age groups found, creating test age group...")
            age_group_response = client.post(
                "/api/age-groups",
                json={"name": "U13"},
                headers=self.headers
            )
            assert age_group_response.status_code == 200
            age_group_id = age_group_response.json()["id"]
        else:
            age_group_id = age_groups[0]["id"]

        print(f"Using age group ID: {age_group_id}")

        # Step 3: Create a team WITH parent_club_id from the start
        print("\n=== Step 3: Creating team with parent_club_id ===")
        team_data = {
            "name": "Test Team With Parent",
            "city": "New York, NY",
            "age_group_ids": [age_group_id],
            "division_id": division_id,
            "parent_club_id": self.created_club_id,  # ✅ Set during creation!
            "academy_team": True
        }

        print(f"Team creation payload: {team_data}")

        team_response = client.post(
            "/api/teams",
            json=team_data,
            headers=self.headers
        )

        print(f"Team creation status: {team_response.status_code}")
        print(f"Team creation response: {team_response.text}")

        assert team_response.status_code == 200, f"Failed to create team: {team_response.text}"

        # Fetch the team to verify parent_club_id was set
        teams_response = client.get("/api/teams", headers=self.headers)
        assert teams_response.status_code == 200
        teams = teams_response.json()
        team = next((t for t in teams if t["name"] == team_data["name"]), None)
        assert team is not None, "Could not find created team"

        team_id = team["id"]
        self.created_team_ids.append(team_id)

        print(f"✅ Team created with ID: {team_id}")
        print(f"   parent_club_id: {team.get('parent_club_id')}")
        print(f"   academy_team: {team.get('academy_team')}")

        # Step 4: Verify parent_club_id was set correctly
        print("\n=== Step 4: Verifying parent_club_id ===")
        assert team.get("parent_club_id") == self.created_club_id, \
            f"Expected parent_club_id={self.created_club_id}, got {team.get('parent_club_id')}"

        print("✅ parent_club_id correctly set during team creation!")

        # Step 5: Verify club shows the team
        print("\n=== Step 5: Verifying club shows team ===")
        club_fetch_response = client.get("/api/clubs", headers=self.headers)
        assert club_fetch_response.status_code == 200
        clubs = club_fetch_response.json()
        fetched_club = next((c for c in clubs if c["id"] == self.created_club_id), None)

        assert fetched_club is not None, "Could not find club"
        print(f"Club team count: {fetched_club.get('team_count', 0)}")

        assert fetched_club.get("team_count", 0) >= 1, \
            f"Expected club to have at least 1 team"

        team_names = [t["name"] for t in fetched_club.get("teams", [])]
        assert "Test Team With Parent" in team_names, \
            f"Expected to find 'Test Team With Parent' in club teams"

        print("✅ All tests passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
