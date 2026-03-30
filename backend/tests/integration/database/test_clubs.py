"""
Comprehensive tests for clubs functionality.
Tests both DAO layer and API endpoints.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required
from dao.club_dao import ClubDAO
from dao.match_dao import SupabaseConnection

# Test client for API tests (unauthenticated)
client = TestClient(app)


def _unique_name(base: str) -> str:
    """Generate a unique club name to avoid parallel test conflicts."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def admin_test_client():
    """TestClient with auth dependency overridden to admin user."""
    mock_admin = {
        "user_id": "test-admin-001",
        "username": "testadmin",
        "email": "admin@example.com",
        "role": "admin",
        "team_id": None,
        "club_id": None,
        "display_name": "Test Admin",
    }

    def override():
        return mock_admin

    app.dependency_overrides[get_current_user_required] = override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


class TestClubsDAO:
    """Test clubs DAO methods."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test database connection with unique names per test."""
        self.conn = SupabaseConnection()
        self.dao = ClubDAO(self.conn)
        self.club_name = _unique_name("Test Club FC")
        self.club_name_2 = _unique_name("Another Club")
        self._created_ids: list[int] = []
        yield
        for club_id in self._created_ids:
            try:
                self.dao.delete_club(club_id)
            except Exception:
                pass

    def _create(self, name: str, city: str = "Boston, MA", **kwargs) -> dict:
        club = self.dao.create_club(name=name, city=city, **kwargs)
        self._created_ids.append(club['id'])
        return club

    def test_create_club(self):
        """Test creating a club."""
        club = self._create(
            name=self.club_name,
            city="Boston, MA",
            website="https://testclub.com",
            description="A test club for unit testing"
        )

        assert club is not None
        assert club['name'] == self.club_name
        assert club['city'] == "Boston, MA"
        assert club['website'] == "https://testclub.com"
        assert 'id' in club
        assert 'created_at' in club

    def test_create_club_minimal(self):
        """Test creating a club with minimal data."""
        club = self._create(name=self.club_name_2, city="Cambridge, MA")

        assert club is not None
        assert club['name'] == self.club_name_2
        assert 'id' in club

    def test_get_all_clubs(self):
        """Test listing all clubs."""
        self._create(name=self.club_name)
        self._create(name=self.club_name_2, city="Cambridge, MA")

        clubs = self.dao.get_all_clubs(include_team_counts=False)
        club_names = [c['name'] for c in clubs]
        assert self.club_name in club_names
        assert self.club_name_2 in club_names

    def test_delete_club(self):
        """Test deleting a club."""
        club = self._create(name=self.club_name)
        club_id = club['id']
        self._created_ids.remove(club_id)  # Will delete manually below

        self.dao.delete_club(club_id)

        clubs = self.dao.get_all_clubs(include_team_counts=False)
        club_ids = [c['id'] for c in clubs]
        assert club_id not in club_ids

    def test_create_duplicate_club_fails(self):
        """Test that creating duplicate club name fails."""
        self._create(name=self.club_name)

        with pytest.raises(Exception):  # noqa: B017
            self._create(name=self.club_name, city="Different City")


class TestClubsAPI:
    """Test clubs API endpoints."""

    def test_get_clubs_requires_auth(self):
        """Test that GET /api/clubs requires authentication."""
        response = client.get("/api/clubs")
        assert response.status_code in [401, 403]

    def test_create_club_requires_admin(self):
        """Test that POST /api/clubs requires admin role."""
        response = client.post("/api/clubs", json={"name": "Test Club", "city": "Boston, MA"})
        assert response.status_code in [401, 403]

    def test_delete_club_requires_admin(self):
        """Test that DELETE /api/clubs/{id} requires admin role."""
        response = client.delete("/api/clubs/99999")
        assert response.status_code in [401, 403]

    def test_get_clubs_authenticated(self, admin_test_client):
        """Test listing clubs with admin auth."""
        response = admin_test_client.get("/api/clubs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
