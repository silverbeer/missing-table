"""Contract tests for profile, photos, customization, and player history endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestProfileContract:
    """Test profile endpoint contracts."""

    def test_get_me_authenticated(self, authenticated_api_client: MissingTableClient):
        """Test getting current user info."""
        result = authenticated_api_client.get_me()
        assert result is not None

    def test_get_me_unauthenticated(self, api_client: MissingTableClient):
        """Test getting current user info without auth fails."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_me()

    def test_check_username_available(self, api_client: MissingTableClient):
        """Test checking username availability."""
        result = api_client.check_username_available("definitely_unused_name_xyz_999")
        assert result is not None


@pytest.mark.contract
class TestProfilePhotoContract:
    """Test profile photo endpoint contracts."""

    def test_upload_profile_photo_requires_auth(self, api_client: MissingTableClient):
        """Test uploading profile photo requires authentication."""
        import os
        import tempfile

        from api_client import AuthenticationError

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            tmp_path = f.name

        try:
            with pytest.raises((AuthenticationError, AuthorizationError)):
                api_client.upload_profile_photo("slot1", tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_delete_profile_photo_requires_auth(self, api_client: MissingTableClient):
        """Test deleting profile photo requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_profile_photo("slot1")

    def test_set_profile_photo_slot_requires_auth(self, api_client: MissingTableClient):
        """Test setting profile photo slot requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.set_profile_photo_slot("slot1")


@pytest.mark.contract
class TestPlayerCustomizationContract:
    """Test player customization endpoint contracts."""

    def test_update_customization_requires_auth(self, api_client: MissingTableClient):
        """Test updating customization requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import PlayerCustomization

        customization = PlayerCustomization()
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_player_customization(customization)


@pytest.mark.contract
class TestPlayerHistoryContract:
    """Test player history endpoint contracts."""

    def test_get_player_history_requires_auth(self, api_client: MissingTableClient):
        """Test getting player history requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_player_history()

    def test_get_current_team_assignment_requires_auth(self, api_client: MissingTableClient):
        """Test getting current team assignment requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_current_team_assignment()

    def test_get_all_current_teams_requires_auth(self, api_client: MissingTableClient):
        """Test getting all current teams requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_all_current_teams()

    def test_create_player_history_requires_auth(self, api_client: MissingTableClient):
        """Test creating player history requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import PlayerHistoryCreate

        history = PlayerHistoryCreate(team_id=1, season_id=1, jersey_number=10)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_player_history(history)

    def test_update_player_history_requires_auth(self, api_client: MissingTableClient):
        """Test updating player history requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import PlayerHistoryUpdate

        update = PlayerHistoryUpdate()
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_player_history(999, update)

    def test_delete_player_history_requires_auth(self, api_client: MissingTableClient):
        """Test deleting player history requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_player_history(999)
