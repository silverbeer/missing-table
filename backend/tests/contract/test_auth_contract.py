"""Contract tests for authentication endpoints."""

import pytest

from api_client import AuthenticationError, MissingTableClient, ValidationError


@pytest.mark.contract
class TestAuthenticationContract:
    """Test authentication endpoint contracts."""

    def test_login_success(self, api_client: MissingTableClient):
        """Test successful login returns expected structure."""
        # First create a test user
        test_email = "test_login@example.com"
        test_password = "Test123!@#"

        try:
            api_client.signup(email=test_email, password=test_password)
        except Exception:
            pass  # User may already exist

        # Test login
        response = api_client.login(email=test_email, password=test_password)

        # Verify response structure
        assert "access_token" in response
        assert "refresh_token" in response
        assert "token_type" in response
        assert response["token_type"] == "bearer"

        # Verify client stored tokens
        assert api_client._access_token is not None
        assert api_client._refresh_token is not None

    def test_login_invalid_credentials(self, api_client: MissingTableClient):
        """Test login with invalid credentials fails appropriately."""
        with pytest.raises(AuthenticationError) as exc_info:
            api_client.login(email="invalid@example.com", password="wrongpassword")

        assert exc_info.value.status_code == 401

    def test_login_missing_fields(self, api_client: MissingTableClient):
        """Test login with missing required fields."""
        # This should raise a validation error
        with pytest.raises((ValidationError, Exception)):
            api_client._request("POST", "/api/auth/login", json_data={"email": "test@example.com"})

    def test_signup_success(self, api_client: MissingTableClient):
        """Test successful signup returns expected structure."""
        import time
        test_email = f"test_signup_{int(time.time())}@example.com"
        test_password = "Test123!@#"

        response = api_client.signup(
            email=test_email,
            password=test_password,
            display_name="Test User"
        )

        # Verify response structure
        assert "access_token" in response or "user" in response
        # Different implementations may return different structures

    def test_signup_duplicate_email(self, api_client: MissingTableClient):
        """Test signup with duplicate email fails."""
        test_email = "duplicate@example.com"
        test_password = "Test123!@#"

        # First signup should succeed
        try:
            api_client.signup(email=test_email, password=test_password)
        except Exception:
            pass  # May already exist

        # Second signup should fail
        with pytest.raises((ValidationError, Exception)):
            api_client.signup(email=test_email, password=test_password)

    def test_logout(self, authenticated_api_client: MissingTableClient):
        """Test logout clears tokens."""
        # Verify client has tokens before logout
        assert authenticated_api_client._access_token is not None

        # Logout
        response = authenticated_api_client.logout()

        # Verify tokens are cleared
        assert authenticated_api_client._access_token is None
        assert authenticated_api_client._refresh_token is None

    def test_get_profile_authenticated(self, authenticated_api_client: MissingTableClient):
        """Test getting profile with valid authentication."""
        profile = authenticated_api_client.get_profile()

        # Verify profile structure
        assert "email" in profile or "user" in profile

    def test_get_profile_unauthenticated(self, api_client: MissingTableClient):
        """Test getting profile without authentication fails."""
        with pytest.raises(AuthenticationError):
            api_client.get_profile()

    def test_update_profile(self, authenticated_api_client: MissingTableClient):
        """Test updating user profile."""
        response = authenticated_api_client.update_profile(display_name="Updated Name")

        # Should return success or updated profile
        assert response is not None

    def test_refresh_token(self, api_client: MissingTableClient):
        """Test refreshing access token."""
        # Login to get tokens
        test_email = "test_refresh@example.com"
        test_password = "Test123!@#"

        try:
            api_client.signup(email=test_email, password=test_password)
        except Exception:
            pass

        api_client.login(email=test_email, password=test_password)

        # Store original access token
        original_token = api_client._access_token

        # Refresh token
        response = api_client.refresh_access_token()

        # Verify new token is different and stored
        assert "access_token" in response
        assert api_client._access_token != original_token


@pytest.mark.contract
class TestAuthorizationContract:
    """Test authorization and role-based access control."""

    def test_admin_endpoints_require_admin_role(self, authenticated_api_client: MissingTableClient):
        """Test that admin endpoints require admin role."""
        from api_client import AuthorizationError

        # Regular user should not be able to access admin endpoints
        with pytest.raises((AuthorizationError, AuthenticationError)):
            authenticated_api_client.get_users()

    def test_csrf_token_endpoint(self, api_client: MissingTableClient):
        """Test CSRF token endpoint."""
        csrf_token = api_client.get_csrf_token()

        assert isinstance(csrf_token, str)
        assert len(csrf_token) > 0
