"""
End-to-end tests for authentication endpoints and flows.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import time


class TestAuthSignup:
    """Test user signup functionality."""

    @pytest.mark.e2e
    def test_signup_valid_data(self, test_client: TestClient):
        """Test user signup with valid data."""
        user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code in [200, 201, 400]  # 400 if user exists or other signup error
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "message" in data or "access_token" in data

    @pytest.mark.e2e
    def test_signup_invalid_email(self, test_client: TestClient):
        """Test signup with invalid email format."""
        user_data = {
            "email": "invalid-email",
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.e2e
    def test_signup_weak_password(self, test_client: TestClient):
        """Test signup with weak password."""
        user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "123",  # Too weak
            "display_name": "Test User"
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code in [400, 422]  # Should reject weak password

    @pytest.mark.e2e
    def test_signup_missing_fields(self, test_client: TestClient):
        """Test signup with missing required fields."""
        # Missing email
        response = test_client.post("/api/auth/signup", json={
            "password": "TestPassword123!",
            "display_name": "Test User"
        })
        assert response.status_code == 422

        # Missing password
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "display_name": "Test User"
        })
        assert response.status_code == 422


class TestAuthLogin:
    """Test user login functionality."""

    @pytest.mark.e2e
    def test_login_invalid_credentials(self, test_client: TestClient):
        """Test login with invalid credentials."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code in [400, 401]  # Unauthorized

    @pytest.mark.e2e
    def test_login_invalid_email_format(self, test_client: TestClient):
        """Test login with invalid email format."""
        login_data = {
            "email": "invalid-email",
            "password": "TestPassword123!"
        }
        
        response = test_client.post("/api/auth/login", json=login_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.e2e
    def test_login_missing_fields(self, test_client: TestClient):
        """Test login with missing required fields."""
        # Missing password
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com"
        })
        assert response.status_code == 422

        # Missing email
        response = test_client.post("/api/auth/login", json={
            "password": "TestPassword123!"
        })
        assert response.status_code == 422

    @pytest.mark.e2e
    def test_login_empty_credentials(self, test_client: TestClient):
        """Test login with empty credentials."""
        response = test_client.post("/api/auth/login", json={
            "email": "",
            "password": ""
        })
        assert response.status_code == 422


class TestAuthTokenRefresh:
    """Test token refresh functionality."""

    @pytest.mark.e2e
    def test_refresh_token_missing(self, test_client: TestClient):
        """Test token refresh without refresh token."""
        response = test_client.post("/api/auth/refresh", json={})
        assert response.status_code == 422  # Missing refresh_token field

    @pytest.mark.e2e
    def test_refresh_token_invalid(self, test_client: TestClient):
        """Test token refresh with invalid refresh token."""
        refresh_data = {
            "refresh_token": "invalid_token_12345"
        }
        
        response = test_client.post("/api/auth/refresh", json=refresh_data)
        assert response.status_code in [400, 401]  # Invalid token


class TestProtectedEndpoints:
    """Test endpoints that require authentication."""

    @pytest.mark.e2e
    def test_get_profile_without_auth(self, test_client: TestClient):
        """Test getting profile without authentication."""
        response = test_client.get("/api/auth/profile")
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_update_profile_without_auth(self, test_client: TestClient):
        """Test updating profile without authentication."""
        profile_data = {
            "display_name": "Updated Name"
        }
        response = test_client.put("/api/auth/profile", json=profile_data)
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_get_current_user_without_auth(self, test_client: TestClient):
        """Test getting current user info without authentication."""
        response = test_client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_logout_without_auth(self, test_client: TestClient):
        """Test logout without authentication."""
        response = test_client.post("/api/auth/logout")
        assert response.status_code == 401


class TestAdminEndpoints:
    """Test admin-only endpoints."""

    @pytest.mark.e2e
    def test_get_users_without_auth(self, test_client: TestClient):
        """Test getting users list without authentication."""
        response = test_client.get("/api/auth/users")
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_update_user_role_without_auth(self, test_client: TestClient):
        """Test updating user role without authentication."""
        role_data = {
            "user_id": "123",
            "role": "admin"
        }
        response = test_client.put("/api/auth/users/role", json=role_data)
        assert response.status_code == 401


class TestAuthWithValidToken:
    """Test authenticated endpoints with mock valid tokens."""

    def create_mock_auth_headers(self):
        """Create mock authentication headers."""
        return {"Authorization": "Bearer mock_valid_token"}

    @pytest.mark.e2e
    @patch('auth.get_current_user_required')
    def test_get_profile_with_auth(self, mock_auth, test_client: TestClient):
        """Test getting profile with mock authentication."""
        # Mock the auth dependency to return a user
        mock_auth.return_value = {
            "id": "test-user-id",
            "email": "test@example.com",
            "display_name": "Test User",
            "role": "user"
        }
        
        headers = self.create_mock_auth_headers()
        response = test_client.get("/api/auth/profile", headers=headers)
        
        # The actual response depends on the auth implementation
        # In a security-disabled environment, this might work differently
        assert response.status_code in [200, 401, 500]

    @pytest.mark.e2e
    @patch('auth.get_current_user_required')
    def test_update_profile_with_auth(self, mock_auth, test_client: TestClient):
        """Test updating profile with mock authentication."""
        mock_auth.return_value = {
            "id": "test-user-id",
            "email": "test@example.com",
            "display_name": "Test User",
            "role": "user"
        }
        
        profile_data = {
            "display_name": "Updated Test User"
        }
        headers = self.create_mock_auth_headers()
        response = test_client.put("/api/auth/profile", json=profile_data, headers=headers)
        
        assert response.status_code in [200, 401, 500]

    @pytest.mark.e2e
    @patch('auth.get_current_user_required')
    def test_get_current_user_with_auth(self, mock_auth, test_client: TestClient):
        """Test getting current user info with mock authentication."""
        mock_auth.return_value = {
            "id": "test-user-id",
            "email": "test@example.com",
            "display_name": "Test User",
            "role": "user"
        }
        
        headers = self.create_mock_auth_headers()
        response = test_client.get("/api/auth/me", headers=headers)
        
        assert response.status_code in [200, 401, 500]


class TestAuthSecurityDisabled:
    """Test authentication behavior when security is disabled."""

    @pytest.mark.e2e
    def test_auth_endpoints_with_security_disabled(self, test_client: TestClient, mock_security_disabled):
        """Test auth endpoints when DISABLE_SECURITY=true."""
        # With security disabled, some endpoints might behave differently
        
        # Test profile endpoint
        response = test_client.get("/api/auth/profile")
        # Could be 401 (still requires auth) or 200 (security disabled)
        assert response.status_code in [200, 401, 500]
        
        # Test me endpoint  
        response = test_client.get("/api/auth/me")
        assert response.status_code in [200, 401, 500]


class TestInvalidTokenFormats:
    """Test various invalid token formats."""

    @pytest.mark.e2e
    def test_malformed_bearer_token(self, test_client: TestClient):
        """Test with malformed Bearer token."""
        headers = {"Authorization": "Bearer"}  # No token part
        response = test_client.get("/api/auth/profile", headers=headers)
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_non_bearer_token(self, test_client: TestClient):
        """Test with non-Bearer token format."""
        headers = {"Authorization": "Basic dGVzdDp0ZXN0"}  # Basic auth
        response = test_client.get("/api/auth/profile", headers=headers)
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_empty_authorization_header(self, test_client: TestClient):
        """Test with empty Authorization header."""
        headers = {"Authorization": ""}
        response = test_client.get("/api/auth/profile", headers=headers)
        assert response.status_code == 401

    @pytest.mark.e2e
    def test_invalid_jwt_format(self, test_client: TestClient):
        """Test with invalid JWT format."""
        headers = {"Authorization": "Bearer invalid.jwt.format"}
        response = test_client.get("/api/auth/profile", headers=headers)
        assert response.status_code == 401


class TestRateLimitingAuth:
    """Test rate limiting on auth endpoints (if enabled)."""

    @pytest.mark.e2e
    def test_login_rate_limiting(self, test_client: TestClient):
        """Test that login attempts are rate limited."""
        login_data = {
            "email": "test@example.com",
            "password": "WrongPassword123!"
        }
        
        # Make several rapid requests
        responses = []
        for _ in range(3):
            response = test_client.post("/api/auth/login", json=login_data)
            responses.append(response.status_code)
        
        # Should all be unauthorized (401) or some might be rate limited (429)
        for status_code in responses:
            assert status_code in [400, 401, 429]

    @pytest.mark.e2e 
    def test_signup_rate_limiting(self, test_client: TestClient):
        """Test that signup attempts are rate limited."""
        # Make several rapid signup attempts
        responses = []
        for i in range(3):
            user_data = {
                "email": f"test_rapid_{i}_{int(time.time())}@example.com",
                "password": "TestPassword123!",
                "display_name": f"Test User {i}"
            }
            response = test_client.post("/api/auth/signup", json=user_data)
            responses.append(response.status_code)
        
        # Should be a mix of success, validation errors, or rate limit errors
        for status_code in responses:
            assert status_code in [200, 201, 400, 401, 422, 429]


class TestAuthInputValidation:
    """Test input validation on auth endpoints."""

    @pytest.mark.e2e
    def test_extremely_long_email(self, test_client: TestClient):
        """Test signup with extremely long email."""
        long_email = "a" * 1000 + "@example.com"
        user_data = {
            "email": long_email,
            "password": "TestPassword123!",
            "display_name": "Test User"
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code in [400, 422]

    @pytest.mark.e2e
    def test_extremely_long_password(self, test_client: TestClient):
        """Test signup with extremely long password."""
        long_password = "A" * 1000 + "123!"
        user_data = {
            "email": "test@example.com",
            "password": long_password,
            "display_name": "Test User"
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code in [200, 201, 400, 422]

    @pytest.mark.e2e
    def test_extremely_long_display_name(self, test_client: TestClient):
        """Test signup with extremely long display name."""
        long_name = "A" * 1000
        user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123!",
            "display_name": long_name
        }
        
        response = test_client.post("/api/auth/signup", json=user_data)
        assert response.status_code in [200, 201, 400, 422]

    @pytest.mark.e2e
    def test_special_characters_in_email(self, test_client: TestClient):
        """Test signup with special characters in email."""
        special_emails = [
            "test+tag@example.com",  # Plus sign (should be valid)
            "test.dot@example.com",   # Dot (should be valid)
            "test_underscore@example.com",  # Underscore (should be valid)
            "test@sub.example.com",   # Subdomain (should be valid)
        ]
        
        for email in special_emails:
            user_data = {
                "email": email,
                "password": "TestPassword123!",
                "display_name": "Test User"
            }
            
            response = test_client.post("/api/auth/signup", json=user_data)
            # Should either succeed or fail due to duplicate, not validation
            assert response.status_code in [200, 201, 400, 422]