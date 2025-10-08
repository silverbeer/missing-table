"""Contract tests for authentication endpoints."""

import pytest

from api_client import AuthenticationError, MissingTableClient, ValidationError


@pytest.mark.contract
@pytest.mark.backend
@pytest.mark.auth
@pytest.mark.api
@pytest.mark.server
class TestAuthenticationContract:
    """Test authentication endpoint contracts."""

    def test_login_success(self, api_client: MissingTableClient):
        """Test successful login returns expected structure."""
        # First create a test user
        test_email = "test_login@example.com"
        test_password = "Test123!@#"  # pragma: allowlist secret

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
            api_client.login(email="invalid@example.com", password="wrongpassword")  # pragma: allowlist secret

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
        test_password = "Test123!@#"  # pragma: allowlist secret

        response = api_client.signup(
            email=test_email,
            password=test_password,
            display_name="Test User"
        )

        # Verify response structure - different implementations may return different structures
        assert "access_token" in response or "user" in response or "user_id" in response

    def test_signup_duplicate_email(self, api_client: MissingTableClient):
        """Test signup with duplicate email fails."""
        test_email = "duplicate@example.com"
        test_password = "Test123!@#"  # pragma: allowlist secret

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

        # Verify profile structure - check for id or user or email
        assert "id" in profile or "email" in profile or "user" in profile

    def test_get_profile_unauthenticated(self, api_client: MissingTableClient):
        """Test getting profile without authentication fails."""
        from api_client import AuthorizationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
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
        test_password = "Test123!@#"  # pragma: allowlist secret

        try:
            api_client.signup(email=test_email, password=test_password)
        except Exception:
            pass

        api_client.login(email=test_email, password=test_password)

        # Store original access token
        original_token = api_client._access_token

        # Refresh token
        response = api_client.refresh_access_token()

        # Verify response contains access_token and client has a token
        # Note: Token may be the same if it hasn't expired yet (which is fine)
        assert "access_token" in response
        assert api_client._access_token is not None


@pytest.mark.contract
class TestSignupWithInviteContract:
    """Test signup with invite code functionality."""

    def test_signup_with_invalid_invite_code(self, api_client: MissingTableClient):
        """Test that signup with invalid invite code fails."""
        import time
        test_email = f"test_invalid_invite_{int(time.time())}@example.com"
        test_password = "Test123!@#"  # pragma: allowlist secret

        # Try to sign up with an invalid invite code
        with pytest.raises(Exception) as exc_info:
            api_client._request(
                "POST",
                "/api/auth/signup",
                json_data={
                    "email": test_email,
                    "password": test_password,
                    "display_name": "Test User",
                    "invite_code": "INVALIDCODE123"
                }
            )

        # Should get a 400 error about invalid invite code
        assert exc_info.value.status_code == 400

    def test_signup_with_expired_invite_code(self, api_client: MissingTableClient):
        """Test that signup with expired invite code fails."""
        import time
        test_email = f"test_expired_invite_{int(time.time())}@example.com"
        test_password = "Test123!@#"  # pragma: allowlist secret

        # Try to sign up with an expired invite code
        # Note: This assumes we have a known expired code or we'd need to create one
        with pytest.raises(Exception) as exc_info:
            api_client._request(
                "POST",
                "/api/auth/signup",
                json_data={
                    "email": test_email,
                    "password": test_password,
                    "display_name": "Test User",
                    "invite_code": "EXPIREDCODE1"
                }
            )

        # Should fail with 400
        assert exc_info.value.status_code == 400

    def test_signup_without_invite_code_still_works(self, api_client: MissingTableClient):
        """Test that signup still works without invite code (backward compatibility)."""
        import time
        test_email = f"test_no_invite_{int(time.time())}@example.com"
        test_password = "Test123!@#"  # pragma: allowlist secret

        # Sign up without invite code should still work
        response = api_client.signup(
            email=test_email,
            password=test_password,
            display_name="Test User No Invite"
        )

        # Should succeed
        assert response is not None
        assert "user_id" in response or "user" in response or "access_token" in response


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
