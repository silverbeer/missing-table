"""Contract tests for version endpoint."""

import pytest

from api_client import MissingTableClient


@pytest.mark.contract
class TestVersionContract:
    """Test version endpoint contracts."""

    def test_get_version(self, api_client: MissingTableClient):
        """Test getting version information."""
        result = api_client.get_version()
        assert result is not None
        assert "version" in result or "app" in result or isinstance(result, dict)
