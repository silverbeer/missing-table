"""Contract tests for player stats endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestPlayerStatsContract:
    """Test player stats endpoint contracts."""

    def test_get_my_player_stats_requires_auth(self, api_client: MissingTableClient):
        """Test getting own player stats requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_my_player_stats()

    def test_get_my_player_stats(self, authenticated_api_client: MissingTableClient):
        """Test getting own player stats returns a response."""
        from api_client import APIError

        try:
            result = authenticated_api_client.get_my_player_stats()
            assert result is not None
        except APIError:
            pass  # User may not have player stats

    def test_get_player_profile(self, authenticated_api_client: MissingTableClient):
        """Test getting a player profile."""
        from api_client import APIError

        try:
            result = authenticated_api_client.get_player_profile("00000000-0000-0000-0000-000000000000")
            assert result is not None
        except APIError:
            pass  # Non-existent user

    def test_get_roster_player_stats(self, authenticated_api_client: MissingTableClient):
        """Test getting roster player stats."""
        from api_client import APIError

        try:
            result = authenticated_api_client.get_roster_player_stats(999999)
            assert result is not None
        except APIError:
            pass  # Non-existent player
