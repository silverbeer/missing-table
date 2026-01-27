"""Contract tests for invite request endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient
from api_client.models import InviteRequestCreate


@pytest.mark.contract
class TestInviteRequestPublicContract:
    """Test public invite request endpoint contracts."""

    def test_create_invite_request(self, api_client: MissingTableClient):
        """Test creating an invite request (public endpoint)."""
        request = InviteRequestCreate(
            email="contract-test@example.com",
            name="Contract Test User",
            team="Test Team",
            reason="Testing",
        )
        result = api_client.create_invite_request(request)
        assert result is not None
        assert result.get("success") is True


@pytest.mark.contract
class TestInviteRequestAdminContract:
    """Test admin invite request endpoint contracts."""

    def test_list_invite_requests_requires_auth(self, api_client: MissingTableClient):
        """Test listing invite requests requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.list_invite_requests()

    def test_get_invite_request_stats_requires_auth(self, api_client: MissingTableClient):
        """Test getting invite request stats requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_invite_request_stats()

    def test_get_invite_request_requires_auth(self, api_client: MissingTableClient):
        """Test getting a specific invite request requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_invite_request("fake-id")

    def test_update_invite_request_status_requires_auth(self, api_client: MissingTableClient):
        """Test updating invite request status requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import InviteRequestStatusUpdate

        update = InviteRequestStatusUpdate(status="approved")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_invite_request_status("fake-id", update)

    def test_delete_invite_request_requires_auth(self, api_client: MissingTableClient):
        """Test deleting an invite request requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_invite_request("fake-id")

    def test_list_invite_requests_admin(self, admin_client: MissingTableClient):
        """Test listing invite requests as admin."""
        requests = admin_client.list_invite_requests()
        assert isinstance(requests, list)

    def test_get_invite_request_stats_admin(self, admin_client: MissingTableClient):
        """Test getting invite request stats as admin."""
        stats = admin_client.get_invite_request_stats()
        assert "total" in stats
        assert "pending" in stats
