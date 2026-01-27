"""Contract tests for clubs endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient, NotFoundError


@pytest.mark.contract
class TestClubsReadContract:
    """Test read operations for clubs endpoints."""

    def test_get_clubs_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting clubs returns a list."""
        clubs = authenticated_api_client.get_clubs()
        assert isinstance(clubs, list)

    def test_get_club_not_found(self, authenticated_api_client: MissingTableClient):
        """Test getting non-existent club returns 404."""
        with pytest.raises(NotFoundError):
            authenticated_api_client.get_club(999999)

    def test_get_club_teams(self, authenticated_api_client: MissingTableClient):
        """Test getting teams for a club."""
        clubs = authenticated_api_client.get_clubs()
        if not clubs:
            pytest.skip("No clubs available")
        teams = authenticated_api_client.get_club_teams(clubs[0]["id"])
        assert isinstance(teams, list)


@pytest.mark.contract
class TestClubsWriteContract:
    """Test write operations for clubs endpoints."""

    def test_create_club_requires_auth(self, api_client: MissingTableClient):
        """Test creating a club requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_club(name="Test Club")

    def test_update_club_requires_auth(self, api_client: MissingTableClient):
        """Test updating a club requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_club(999, name="Updated")

    def test_delete_club_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a club requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_club(999)

    def test_upload_club_logo_requires_auth(self, api_client: MissingTableClient):
        """Test uploading club logo requires authentication."""
        import tempfile

        from api_client import AuthenticationError

        # Create a tiny temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp_path = f.name

        try:
            with pytest.raises((AuthenticationError, AuthorizationError)):
                api_client.upload_club_logo(999, tmp_path)
        finally:
            import os
            os.unlink(tmp_path)
