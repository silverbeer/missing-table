"""
TSC Journey Tests - Phase 1: Club Manager Journey.

This phase tests the club manager user experience:
- Validate and use invite to sign up
- Login as club manager
- View club details
- Create club fan invite

Run: pytest tests/tsc/test_01_club_manager.py -v
"""

import pytest

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestClubManagerJourney:
    """Phase 1: Club manager signs up and manages club."""

    def test_01_validate_club_manager_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate the club manager invite code."""
        # Find club manager invite
        club_mgr_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "club_manager" and inv["status"] == "pending"
        ]
        assert len(club_mgr_invites) > 0, "No club manager invite found"

        invite_code = club_mgr_invites[0]["code"]
        result = tsc_client.validate_invite(invite_code)

        assert result is not None
        assert result.get("invite_type") == "club_manager" or "club_id" in result
        print(f"Validated club manager invite: {invite_code}")

    def test_02_signup_club_manager(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Sign up as club manager using invite."""
        # Find club manager invite
        club_mgr_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "club_manager" and inv["status"] == "pending"
        ]
        invite_code = club_mgr_invites[0]["code"]

        result = tsc_client.signup_with_invite(
            username=tsc_config.full_club_manager_username,
            password=tsc_config.club_manager_password,
            invite_code=invite_code,
            display_name="TSC Club Manager",
        )

        assert "user" in result or "id" in result or "message" in result
        print(f"Signed up club manager: {tsc_config.full_club_manager_username}")

        # Mark invite as used
        club_mgr_invites[0]["status"] = "used"

    def test_03_login_club_manager(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Login as club manager."""
        result = tsc_client.login_club_manager()

        assert "access_token" in result or "session" in result
        print(f"Logged in as club manager: {tsc_config.full_club_manager_username}")

    def test_04_view_club(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View club details."""
        result = tsc_client.get_club()

        assert result is not None
        assert result.get("id") == entity_registry.club_id
        print(f"Viewed club: {result.get('name')}")

    def test_05_view_club_teams(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View teams in the club."""
        result = tsc_client.get_club_teams()

        assert isinstance(result, list)
        # Teams may or may not be associated with club yet
        print(f"Club has {len(result)} teams")

    def test_06_get_profile(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Get club manager profile."""
        result = tsc_client.get_profile()

        assert result is not None
        # Profile should show club_manager role after invite signup
        print(f"Profile: {result.get('username', result.get('display_name'))}, Role: {result.get('role')}")

    def test_07_update_profile(self, tsc_client: TSCClient):
        """Update club manager profile."""
        result = tsc_client.update_profile(display_name="TSC Club Manager (Updated)")

        assert result is not None
        print("Updated club manager profile")

    def test_08_create_club_fan_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create invite for club fan."""
        result = tsc_client.create_club_fan_invite()

        assert "invite_code" in result
        assert len(result["invite_code"]) == 12
        print(f"Created club fan invite: {result['invite_code']}")

    def test_09_verify_club_manager_journey(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify club manager journey completed successfully."""
        # Check that club fan invite was created
        club_fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "club_fan" and inv["status"] == "pending"
        ]
        assert len(club_fan_invites) > 0, "Club fan invite not created"

        print("\n=== Phase 1 Complete ===")
        print(f"Club manager signed up and logged in")
        print(f"Club fan invite created: {club_fan_invites[0]['code']}")
        print(f"Total invites: {len(entity_registry.invites)}")
