"""Contract tests for admin cache management endpoints."""

import pytest

from api_client import AuthenticationError, AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestCacheContract:
    """Test admin cache management endpoint contracts."""

    def test_get_cache_stats_requires_auth(self, api_client: MissingTableClient):
        """Test getting cache stats requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_cache_stats()

    def test_clear_all_cache_requires_auth(self, api_client: MissingTableClient):
        """Test clearing all cache requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.clear_all_cache()

    def test_clear_cache_by_type_requires_auth(self, api_client: MissingTableClient):
        """Test clearing cache by type requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.clear_cache_by_type("standings")

    def test_get_cache_stats_admin(self, admin_client: MissingTableClient):
        """Test getting cache stats as admin."""
        stats = admin_client.get_cache_stats()
        assert isinstance(stats, dict)
        assert "enabled" in stats

    def test_clear_cache_by_type_invalid(self, admin_client: MissingTableClient):
        """Test clearing cache with invalid type returns error."""
        from api_client import APIError

        with pytest.raises(APIError):
            admin_client.clear_cache_by_type("invalid_type")
