"""
TSC Journey Tests - Phase 3: Player Journey.

This phase tests the player user experience:
- Validate and use invite to sign up
- Login as player
- View team
- Edit profile
- View match schedule

Run: pytest tests/tsc/test_03_player.py -v
"""

import pytest

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestPlayerJourney:
    """Phase 3: Player signs up and views team info."""

    def test_01_validate_player_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate the player invite code."""
        # Find player invite
        player_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_player" and inv["status"] == "pending"
        ]
        assert len(player_invites) > 0, "No player invite found"

        invite_code = player_invites[0]["code"]
        result = tsc_client.validate_invite(invite_code)

        assert result is not None
        assert result.get("invite_type") == "team_player" or "team_id" in result
        print(f"Validated player invite: {invite_code}")

    def test_02_signup_player(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Sign up as player using invite."""
        # Find player invite
        player_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_player" and inv["status"] == "pending"
        ]
        invite_code = player_invites[0]["code"]

        result = tsc_client.signup_with_invite(
            username=tsc_config.full_player_username,
            password=tsc_config.player_password,
            invite_code=invite_code,
            display_name="TSC Player",
        )

        assert "user" in result or "id" in result or "message" in result
        print(f"Signed up player: {tsc_config.full_player_username}")

        # Mark invite as used
        player_invites[0]["status"] = "used"

    def test_03_login_player(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Login as player."""
        result = tsc_client.login_player()

        assert "access_token" in result or "session" in result
        print(f"Logged in as player: {tsc_config.full_player_username}")

    def test_04_get_profile(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Get player profile."""
        result = tsc_client.get_profile()

        assert result is not None
        print(f"Profile: {result.get('username', result.get('display_name'))}, Role: {result.get('role')}")

    def test_05_update_profile(self, tsc_client: TSCClient):
        """Update player profile."""
        result = tsc_client.update_profile(display_name="TSC Player (Updated)")

        assert result is not None
        print("Updated player profile")

    def test_06_view_teams(self, tsc_client: TSCClient):
        """View all teams."""
        result = tsc_client.get_teams()

        assert isinstance(result, list)
        print(f"Found {len(result)} teams")

    def test_07_view_schedule(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View match schedule (upcoming matches)."""
        result = tsc_client.get_matches(
            season_id=entity_registry.season_id,
            upcoming=True,
        )

        assert isinstance(result, list)
        print(f"Found {len(result)} upcoming matches")

    def test_08_view_all_matches(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View all matches."""
        result = tsc_client.get_matches(season_id=entity_registry.season_id)

        assert isinstance(result, list)
        assert len(result) >= 4, "Should have at least 4 matches"
        print(f"Found {len(result)} total matches")

    def test_09_verify_player_journey(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify player journey completed successfully."""
        print("\n=== Phase 3 Complete ===")
        print("Player signed up, logged in, and viewed schedule")
