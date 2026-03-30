"""
End-to-end tests for FastAPI API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthCheckEndpoints:
    """Test health check endpoints."""

    @pytest.mark.e2e
    def test_health_check(self, test_client: TestClient):
        """Test basic health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.e2e
    def test_full_health_check(self, test_client: TestClient):
        """Test comprehensive health check endpoint."""
        response = test_client.get("/health/full")
        assert response.status_code in [200, 503]  # 503 if database unavailable
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "api" in data["checks"]

        # API should always be healthy if we got a response
        assert data["checks"]["api"]["status"] == "healthy"


class TestReferenceDataEndpoints:
    """Test reference data endpoints (all require authentication)."""

    @pytest.mark.e2e
    def test_get_age_groups(self, authenticated_client: TestClient):
        """Test getting all age groups."""
        response = authenticated_client.get("/api/age-groups")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_seasons(self, authenticated_client: TestClient):
        """Test getting all seasons."""
        response = authenticated_client.get("/api/seasons")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_current_season(self, authenticated_client: TestClient):
        """Test getting current season."""
        response = authenticated_client.get("/api/current-season")
        assert response.status_code in [200, 404]  # 404 if no current season
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "name" in data

    @pytest.mark.e2e
    def test_get_active_seasons(self, authenticated_client: TestClient):
        """Test getting active seasons."""
        response = authenticated_client.get("/api/active-seasons")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_match_types(self, authenticated_client: TestClient):
        """Test getting all match types."""
        response = authenticated_client.get("/api/match-types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_divisions(self, authenticated_client: TestClient):
        """Test getting all divisions."""
        response = authenticated_client.get("/api/divisions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_positions(self, authenticated_client: TestClient):
        """Test getting all player positions."""
        response = authenticated_client.get("/api/positions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestTeamsEndpoints:
    """Test team-related endpoints."""

    @pytest.mark.e2e
    def test_get_teams(self, authenticated_client: TestClient):
        """Test getting all teams."""
        response = authenticated_client.get("/api/teams")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_teams_with_filters(self, authenticated_client: TestClient):
        """Test getting teams with filters."""
        # Test with game_type_id filter
        response = authenticated_client.get("/api/teams?game_type_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with age_group_id filter
        response = authenticated_client.get("/api/teams?age_group_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with both filters
        response = authenticated_client.get("/api/teams?game_type_id=1&age_group_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_teams_with_invalid_filters(self, authenticated_client: TestClient):
        """Test getting teams with invalid filters."""
        response = authenticated_client.get("/api/teams?game_type_id=999999")
        assert response.status_code == 200  # Should return empty list, not error
        data = response.json()
        assert isinstance(data, list)


class TestMatchesEndpoints:
    """Test match-related endpoints."""

    @pytest.mark.e2e
    def test_get_matches(self, authenticated_client: TestClient):
        """Test getting all matches."""
        response = authenticated_client.get("/api/matches")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_matches_with_filters(self, authenticated_client: TestClient):
        """Test getting matches with various filters."""
        # Test with season filter
        response = authenticated_client.get("/api/matches?season_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with age group filter
        response = authenticated_client.get("/api/matches?age_group_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with match type filter
        response = authenticated_client.get("/api/matches?match_type_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with limit
        response = authenticated_client.get("/api/matches?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_check_match(self, authenticated_client: TestClient):
        """Test the check match endpoint."""
        response = authenticated_client.get(
            "/api/check-match?date=2024-03-15&homeTeam=Test%20Team&awayTeam=Other%20Team"
        )
        assert response.status_code in [200, 404]  # 404 if match not found


class TestLeagueTableEndpoints:
    """Test league table endpoints."""

    @pytest.mark.e2e
    def test_get_table(self, authenticated_client: TestClient):
        """Test getting league table."""
        response = authenticated_client.get("/api/table")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.e2e
    def test_get_table_with_filters(self, authenticated_client: TestClient):
        """Test getting league table with filters."""
        # Test with season filter
        response = authenticated_client.get("/api/table?season_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with age group filter
        response = authenticated_client.get("/api/table?age_group_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with game type filter
        response = authenticated_client.get("/api/table?game_type_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Test with multiple filters
        response = authenticated_client.get("/api/table?season_id=1&age_group_id=1&game_type_id=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestUnauthorizedEndpoints:
    """Test endpoints that should require authentication but are called without auth."""

    @pytest.mark.e2e
    def test_create_team_unauthorized(self, test_client: TestClient):
        """Test creating team without auth should fail."""
        team_data = {
            "name": "Test Team",
            "city": "Test City",
            "age_group_ids": [1]
        }
        response = test_client.post("/api/teams", json=team_data)
        assert response.status_code in [403, 422, 500]  # Auth failure or validation error

    @pytest.mark.e2e
    def test_create_match_unauthorized(self, test_client: TestClient):
        """Test creating match without auth should fail with 403."""
        match_data = {
            "home_team_id": 1,
            "away_team_id": 2,
            "match_date": "2024-03-15",
            "season_id": 1,
            "age_group_id": 1,
            "match_type_id": 1,
        }
        response = test_client.post("/api/matches", json=match_data)
        assert response.status_code == 403

    @pytest.mark.e2e
    def test_admin_endpoints_unauthorized(self, test_client: TestClient):
        """Test admin endpoints without auth should fail."""
        # Test creating age group
        response = test_client.post("/api/age-groups", json={"name": "U15"})
        assert response.status_code == 403  # Forbidden (no auth token)

        # Test creating season
        response = test_client.post("/api/seasons", json={"name": "2025-2026"})
        assert response.status_code == 403

        # Test creating division
        response = test_client.post("/api/divisions", json={"name": "Premier"})
        assert response.status_code == 403

        # Test getting users
        response = test_client.get("/api/auth/users")
        assert response.status_code == 403


class TestCSRFEndpoint:
    """Test CSRF token endpoint."""

    @pytest.mark.e2e
    def test_get_csrf_token(self, test_client: TestClient):
        """Test getting CSRF token."""
        response = test_client.get("/api/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert isinstance(data["csrf_token"], str)
        assert len(data["csrf_token"]) > 0


class TestErrorHandling:
    """Test error handling across various scenarios."""

    @pytest.mark.e2e
    def test_invalid_endpoints(self, test_client: TestClient):
        """Test invalid endpoints return 404."""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

        response = test_client.post("/api/invalid-endpoint")
        assert response.status_code == 404

    @pytest.mark.e2e
    def test_invalid_http_methods(self, test_client: TestClient):
        """Test invalid HTTP methods return appropriate errors."""
        # POST on teams endpoint returns 403 (auth check before method check)
        response = test_client.post("/api/teams")
        assert response.status_code in [403, 401, 405, 422]

        # Try DELETE on GET-only endpoint
        response = test_client.delete("/api/seasons")
        assert response.status_code == 405

    @pytest.mark.e2e
    def test_invalid_json_payloads(self, test_client: TestClient):
        """Test invalid JSON payloads are handled properly."""
        response = test_client.post(
            "/api/teams",
            data="{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 401, 403, 422]

    @pytest.mark.e2e
    def test_large_limit_parameters(self, authenticated_client: TestClient):
        """Test that large limit parameters are handled gracefully."""
        response = authenticated_client.get("/api/matches?limit=999999")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
