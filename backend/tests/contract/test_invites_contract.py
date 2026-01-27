"""Contract tests for invite endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestInviteValidationContract:
    """Test invite validation endpoint contracts."""

    def test_validate_invalid_invite(self, api_client: MissingTableClient):
        """Test validating an invalid invite code."""
        from api_client import APIError

        with pytest.raises(APIError):
            api_client.validate_invite("INVALID_CODE_123")

    def test_get_my_invites_requires_auth(self, api_client: MissingTableClient):
        """Test getting my invites requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_my_invites()

    def test_get_my_invites(self, authenticated_api_client: MissingTableClient):
        """Test getting invites for authenticated user."""
        invites = authenticated_api_client.get_my_invites()
        assert isinstance(invites, list)

    def test_cancel_invite_requires_auth(self, api_client: MissingTableClient):
        """Test cancelling an invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.cancel_invite("fake-id")


@pytest.mark.contract
class TestAdminInviteContract:
    """Test admin invite creation endpoint contracts."""

    def test_create_club_manager_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating club manager invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_manager_invite(1)

    def test_create_team_manager_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team manager invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_manager_invite(1, 1)

    def test_create_team_player_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating team player invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_player_invite_admin(1, 1)

    def test_create_team_fan_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating team fan invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_fan_invite_admin(1, 1)

    def test_create_club_fan_invite_admin_requires_auth(self, api_client: MissingTableClient):
        """Test creating club fan invite (admin) requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_fan_invite_admin(1)


@pytest.mark.contract
class TestManagerInviteContract:
    """Test manager invite creation endpoint contracts."""

    def test_create_club_fan_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating club fan invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club_fan_invite(1)

    def test_create_team_player_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team player invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_player_invite(1, 1)

    def test_create_team_fan_invite_requires_auth(self, api_client: MissingTableClient):
        """Test creating team fan invite requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_fan_invite(1, 1)

    def test_get_team_manager_assignments_requires_auth(self, api_client: MissingTableClient):
        """Test getting team manager assignments requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_team_manager_assignments()
