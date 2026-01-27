"""Contract tests for team mapping endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestTeamMappingsContract:
    """Test team mapping endpoint contracts."""

    def test_create_team_mapping_requires_auth(self, api_client: MissingTableClient):
        """Test creating a team mapping requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team_mapping(1, 1, 1)

    def test_delete_team_mapping_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a team mapping requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_team_mapping(1, 1, 1)
