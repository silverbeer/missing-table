"""
Integration tests for /api/matches endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from app import app
from auth import get_current_user_required


@pytest.fixture
def authenticated_client():
    """TestClient with auth dependency overridden to an admin user."""
    mock_user = {
        "user_id": "test-admin-001",
        "username": "testadmin",
        "email": "admin@example.com",
        "role": "admin",
        "team_id": None,
        "club_id": None,
        "display_name": "Test Admin",
    }

    def override():
        return mock_user

    app.dependency_overrides[get_current_user_required] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user_required, None)


@pytest.fixture
def unauthenticated_client():
    """Plain TestClient with no auth override."""
    with TestClient(app) as client:
        yield client


def test_get_all_matches(authenticated_client):
    """Test retrieving all matches returns a list."""
    response = authenticated_client.get("/api/matches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_matches_with_limit(authenticated_client):
    """Test matches endpoint respects limit parameter."""
    response = authenticated_client.get("/api/matches", params={"limit": 10})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10


def test_get_matches_with_filters(authenticated_client):
    """Test matches endpoint accepts filter parameters."""
    response = authenticated_client.get("/api/matches", params={"season_id": 1})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_add_match_missing_fields(authenticated_client):
    """Test adding a match with missing required fields returns 422."""
    response = authenticated_client.post("/api/matches", json={
        "home_team_id": 1
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_match_invalid_data_types(authenticated_client):
    """Test adding a match with invalid data types returns 422."""
    response = authenticated_client.post("/api/matches", json={
        "home_team_id": "not-an-int",
        "away_team_id": "not-an-int",
        "match_date": "invalid-date",
    })
    assert response.status_code == 422


def test_unauthorized_access_to_matches(unauthenticated_client):
    """Test that unauthenticated access to matches returns 403."""
    response = unauthenticated_client.get("/api/matches")
    assert response.status_code == 403


def test_unauthorized_post_match(unauthenticated_client):
    """Test that unauthenticated POST to matches returns 403."""
    response = unauthenticated_client.post("/api/matches", json={
        "home_team_id": 1,
        "away_team_id": 2,
        "match_date": "2024-03-15",
    })
    assert response.status_code == 403
