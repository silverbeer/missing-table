"""Contract tests for leagues endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient, NotFoundError


@pytest.mark.contract
class TestLeaguesContract:
    """Test leagues endpoint contracts."""

    def test_get_leagues_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting leagues returns a list."""
        leagues = authenticated_api_client.get_leagues()
        assert isinstance(leagues, list)

    def test_get_league_not_found(self, authenticated_api_client: MissingTableClient):
        """Test getting non-existent league returns 404."""
        with pytest.raises(NotFoundError):
            authenticated_api_client.get_league(999999)

    def test_create_league_requires_auth(self, api_client: MissingTableClient):
        """Test creating a league requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_league(name="Test League")

    def test_update_league_requires_auth(self, api_client: MissingTableClient):
        """Test updating a league requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_league(999, name="Updated")

    def test_delete_league_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a league requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_league(999)
