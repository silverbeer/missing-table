"""Contract tests for lineup endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestLineupContract:
    """Test lineup endpoint contracts."""

    def test_get_lineup(self, authenticated_api_client: MissingTableClient):
        """Test getting a lineup for a match/team returns a response."""
        from api_client import APIError

        try:
            result = authenticated_api_client.get_lineup(999999, 1)
            # Result may be None (no lineup) or a dict — both are valid
            assert result is None or isinstance(result, dict)
        except APIError:
            pass  # Expected for non-existent match

    def test_save_lineup_requires_auth(self, api_client: MissingTableClient):
        """Test saving a lineup requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import LineupSave

        lineup = LineupSave(formation_name="4-3-3", positions=[])
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.save_lineup(1, 1, lineup)
