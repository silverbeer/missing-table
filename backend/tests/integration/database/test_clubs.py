"""
Comprehensive tests for clubs functionality.
Tests both DAO layer and API endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from app import app
from dao.match_dao import MatchDAO, SupabaseConnection

# Test client for API tests
client = TestClient(app)

# Test data
TEST_CLUB = {
    "name": "Test Club FC",
    "city": "Boston, MA",
    "website": "https://testclub.com",
    "description": "A test club for unit testing"
}

TEST_CLUB_2 = {
    "name": "Another Club",
    "city": "Cambridge, MA"
}


class TestClubsDAO:
    """Test clubs DAO methods."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test database connection."""
        self.conn = SupabaseConnection()
        self.dao = MatchDAO(self.conn)
        yield
        # Cleanup after each test
        try:
            clubs = self.dao.get_all_clubs()
            for club in clubs:
                if club['name'] in [TEST_CLUB['name'], TEST_CLUB_2['name']]:
                    self.dao.delete_club(club['id'])
        except Exception:  # noqa: S110 - test cleanup should not fail on missing tables
            # Ignore cleanup errors (table may not exist yet)
            pass

    def test_create_club(self):
        """Test creating a club."""
        club = self.dao.create_club(
            name=TEST_CLUB['name'],
            city=TEST_CLUB['city'],
            website=TEST_CLUB['website'],
            description=TEST_CLUB['description']
        )

        assert club is not None
        assert club['name'] == TEST_CLUB['name']
        assert club['city'] == TEST_CLUB['city']
        assert club['website'] == TEST_CLUB['website']
        assert club['description'] == TEST_CLUB['description']
        assert 'id' in club
        assert 'created_at' in club

    def test_create_club_minimal(self):
        """Test creating a club with minimal data."""
        club = self.dao.create_club(
            name=TEST_CLUB_2['name'],
            city=TEST_CLUB_2['city']
        )

        assert club is not None
        assert club['name'] == TEST_CLUB_2['name']
        assert club['city'] == TEST_CLUB_2['city']
        assert 'id' in club

    def test_get_all_clubs(self):
        """Test listing all clubs."""
        # Create test clubs
        self.dao.create_club(name=TEST_CLUB['name'], city=TEST_CLUB['city'])
        self.dao.create_club(name=TEST_CLUB_2['name'], city=TEST_CLUB_2['city'])

        # Get all clubs
        clubs = self.dao.get_all_clubs()

        assert len(clubs) >= 2
        club_names = [c['name'] for c in clubs]
        assert TEST_CLUB['name'] in club_names
        assert TEST_CLUB_2['name'] in club_names

    def test_get_club_teams(self):
        """Test getting teams for a club."""
        # Create a club
        club = self.dao.create_club(name=TEST_CLUB['name'], city=TEST_CLUB['city'])

        # Get teams (should be empty initially)
        teams = self.dao.get_club_teams(club['id'])

        assert isinstance(teams, list)
        # Initially empty, would have teams after linking teams to club

    def test_delete_club(self):
        """Test deleting a club."""
        # Create a club
        club = self.dao.create_club(name=TEST_CLUB['name'], city=TEST_CLUB['city'])
        club_id = club['id']

        # Delete it
        self.dao.delete_club(club_id)

        # Verify it's gone
        clubs = self.dao.get_all_clubs()
        club_ids = [c['id'] for c in clubs]
        assert club_id not in club_ids

    def test_create_duplicate_club_fails(self):
        """Test that creating duplicate club name fails."""
        # Create first club
        self.dao.create_club(name=TEST_CLUB['name'], city=TEST_CLUB['city'])

        # Try to create duplicate - should raise an exception
        with pytest.raises(Exception):  # noqa: B017 - checking any failure for duplicate
            self.dao.create_club(name=TEST_CLUB['name'], city="Different City")


class TestClubsAPI:
    """Test clubs API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        self.conn = SupabaseConnection()
        self.dao = MatchDAO(self.conn)
        yield
        # Cleanup
        try:
            clubs = self.dao.get_all_clubs()
            for club in clubs:
                if club['name'] in [TEST_CLUB['name'], TEST_CLUB_2['name']]:
                    self.dao.delete_club(club['id'])
        except Exception:  # noqa: S110 - test cleanup should not fail on missing tables
            # Ignore cleanup errors (table may not exist yet)
            pass

    def test_get_clubs_requires_auth(self):
        """Test that GET /api/clubs requires authentication."""
        response = client.get("/api/clubs")
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    def test_create_club_requires_admin(self):
        """Test that POST /api/clubs requires admin role."""
        response = client.post(
            "/api/clubs",
            json=TEST_CLUB
        )
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    def test_delete_club_requires_admin(self):
        """Test that DELETE /api/clubs/{id} requires admin role."""
        # Create a club first
        club = self.dao.create_club(name=TEST_CLUB['name'], city=TEST_CLUB['city'])

        response = client.delete(f"/api/clubs/{club['id']}")
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    # TODO: Add authenticated tests once we have test auth tokens
    # def test_create_club_authenticated(self):
    #     """Test creating club with admin auth."""
    #     pass

    # def test_get_clubs_authenticated(self):
    #     """Test listing clubs with auth."""
    #     pass

    # def test_delete_club_authenticated(self):
    #     """Test deleting club with admin auth."""
    #     pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
