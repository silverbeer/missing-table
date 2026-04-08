"""Contract tests for channel access request endpoints."""

import pytest

from api_client import AuthenticationError, AuthorizationError, MissingTableClient
from api_client.models import ChannelAccessRequestCreate, ChannelAccessStatusUpdate


@pytest.mark.contract
class TestChannelRequestAuthContract:
    """Test that channel request endpoints enforce authentication."""

    def test_get_my_request_requires_auth(self, api_client: MissingTableClient):
        """GET /me requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_my_channel_request()

    def test_create_request_requires_auth(self, api_client: MissingTableClient):
        """POST / requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_channel_request(
                ChannelAccessRequestCreate(telegram=True, telegram_handle="testuser")
            )

    def test_list_requests_requires_auth(self, api_client: MissingTableClient):
        """GET / (admin list) requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.list_channel_requests()

    def test_stats_requires_auth(self, api_client: MissingTableClient):
        """GET /stats requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_channel_request_stats()

    def test_update_status_requires_auth(self, api_client: MissingTableClient):
        """PUT /{id}/status requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_channel_request_status(
                "fake-id",
                ChannelAccessStatusUpdate(platform="telegram", status="approved"),
            )

    def test_delete_requires_auth(self, api_client: MissingTableClient):
        """DELETE /{id} requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_channel_request("fake-id")


@pytest.mark.contract
class TestChannelRequestAdminContract:
    """Test admin channel request endpoint contracts."""

    def test_list_as_admin(self, admin_client: MissingTableClient):
        """Admin can list channel requests; result is a list."""
        requests = admin_client.list_channel_requests()
        assert isinstance(requests, list)

    def test_list_with_status_filter(self, admin_client: MissingTableClient):
        """Admin can filter by status."""
        requests = admin_client.list_channel_requests(status="pending")
        assert isinstance(requests, list)

    def test_list_with_platform_filter(self, admin_client: MissingTableClient):
        """Admin can filter by platform."""
        requests = admin_client.list_channel_requests(platform="telegram")
        assert isinstance(requests, list)

    def test_stats_as_admin(self, admin_client: MissingTableClient):
        """Admin gets stats with correct keys."""
        stats = admin_client.get_channel_request_stats()
        assert "total" in stats
        assert "pending_telegram" in stats
        assert "pending_discord" in stats
        assert "pending_total" in stats
        assert "approved" in stats
        assert "denied" in stats

    def test_stats_values_are_non_negative(self, admin_client: MissingTableClient):
        """All stat counts are non-negative integers."""
        stats = admin_client.get_channel_request_stats()
        for key in ("total", "pending_telegram", "pending_discord", "pending_total", "approved", "denied"):
            assert isinstance(stats[key], int)
            assert stats[key] >= 0

    def test_get_nonexistent_request(self, admin_client: MissingTableClient):
        """Fetching a non-existent request returns 404."""
        from api_client import NotFoundError

        with pytest.raises(NotFoundError):
            admin_client.get_channel_request("00000000-0000-0000-0000-000000000000")
