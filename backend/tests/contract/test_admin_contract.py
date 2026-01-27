"""Contract tests for admin player management and user profile endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestAdminPlayerContract:
    """Test admin player management endpoint contracts."""

    def test_get_admin_players_requires_auth(self, api_client: MissingTableClient):
        """Test getting admin players requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_admin_players()

    def test_update_admin_player_requires_auth(self, api_client: MissingTableClient):
        """Test updating admin player requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import AdminPlayerUpdate

        update = AdminPlayerUpdate()
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_admin_player(999, update)

    def test_add_admin_player_team_requires_auth(self, api_client: MissingTableClient):
        """Test adding admin player team requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import AdminPlayerTeamAssignment

        assignment = AdminPlayerTeamAssignment(team_id=1, season_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.add_admin_player_team(999, assignment)

    def test_end_admin_player_team_requires_auth(self, api_client: MissingTableClient):
        """Test ending admin player team requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.end_admin_player_team(999)

    def test_get_admin_players_admin(self, admin_client: MissingTableClient):
        """Test getting admin players as admin."""
        players = admin_client.get_admin_players()
        assert isinstance(players, list)


@pytest.mark.contract
class TestAdminUserProfileContract:
    """Test admin user profile endpoint contracts."""

    def test_admin_update_user_profile_requires_auth(self, api_client: MissingTableClient):
        """Test updating user profile requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import UserProfileUpdate

        profile = UserProfileUpdate(user_id="fake-user-id")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.admin_update_user_profile(profile)
