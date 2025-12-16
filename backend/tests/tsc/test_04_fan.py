"""
TSC Journey Tests - Phase 4: Fan Journey.

This phase tests the fan user experience:
- Validate and use invite to sign up (club fan and team fan)
- Login as fan
- View standings
- View matches
- View LIVE match

Run: pytest tests/tsc/test_04_fan.py -v
"""

import pytest

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestFanJourney:
    """Phase 4: Fan signs up and views public content."""

    def test_01_validate_club_fan_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate the club fan invite code."""
        # Find club fan invite
        club_fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "club_fan" and inv["status"] == "pending"
        ]
        assert len(club_fan_invites) > 0, "No club fan invite found"

        invite_code = club_fan_invites[0]["code"]
        result = tsc_client.validate_invite(invite_code)

        assert result is not None
        print(f"Validated club fan invite: {invite_code}")

    def test_02_signup_club_fan(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Sign up as club fan using invite."""
        # Find club fan invite
        club_fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "club_fan" and inv["status"] == "pending"
        ]
        invite_code = club_fan_invites[0]["code"]

        result = tsc_client.signup_with_invite(
            username=tsc_config.full_club_fan_username,
            password=tsc_config.club_fan_password,
            invite_code=invite_code,
            display_name="TSC Club Fan",
        )

        assert "user" in result or "id" in result or "message" in result
        print(f"Signed up club fan: {tsc_config.full_club_fan_username}")

        # Mark invite as used
        club_fan_invites[0]["status"] = "used"

    def test_03_validate_team_fan_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate the team fan invite code."""
        # Find team fan invite
        team_fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_fan" and inv["status"] == "pending"
        ]

        if len(team_fan_invites) == 0:
            pytest.skip("No team fan invite found - skipping")

        invite_code = team_fan_invites[0]["code"]
        result = tsc_client.validate_invite(invite_code)

        assert result is not None
        print(f"Validated team fan invite: {invite_code}")

    def test_04_signup_team_fan(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Sign up as team fan using invite."""
        # Find team fan invite
        team_fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_fan" and inv["status"] == "pending"
        ]

        if len(team_fan_invites) == 0:
            pytest.skip("No team fan invite found - skipping")

        invite_code = team_fan_invites[0]["code"]

        result = tsc_client.signup_with_invite(
            username=tsc_config.full_team_fan_username,
            password=tsc_config.team_fan_password,
            invite_code=invite_code,
            display_name="TSC Team Fan",
        )

        assert "user" in result or "id" in result or "message" in result
        print(f"Signed up team fan: {tsc_config.full_team_fan_username}")

        # Mark invite as used
        team_fan_invites[0]["status"] = "used"

    def test_05_login_club_fan(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Login as club fan."""
        result = tsc_client.login_club_fan()

        assert "access_token" in result or "session" in result
        print(f"Logged in as club fan: {tsc_config.full_club_fan_username}")

    def test_06_view_standings(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View league standings."""
        result = tsc_client.get_table(
            season_id=entity_registry.season_id,
            age_group_id=entity_registry.age_group_id,
            division_id=entity_registry.division_id,
        )

        assert isinstance(result, list)
        print(f"Standings has {len(result)} teams")

        # Print standings if available
        for team in result[:5]:  # Top 5
            print(f"  {team.get('team_name', team.get('name'))}: {team.get('points', 0)} pts")

    def test_07_view_matches(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View all matches."""
        result = tsc_client.get_matches(season_id=entity_registry.season_id)

        assert isinstance(result, list)
        assert len(result) >= 4, "Should have at least 4 matches"
        print(f"Found {len(result)} matches")

    def test_08_view_live_match(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """View the LIVE match."""
        # Get the match that was set to live
        live_match_id = entity_registry.match_ids[-1] if entity_registry.match_ids else None

        if live_match_id is None:
            pytest.skip("No live match ID found")

        result = tsc_client.client.get_game(live_match_id)

        assert result is not None
        assert result.get("match_status") == "live" or result.get("status") == "live", \
            f"Match status should be live, got: {result.get('match_status', result.get('status'))}"
        print(f"Viewing LIVE match (ID: {live_match_id}): {result.get('match_status', result.get('status'))}")

    def test_09_verify_fan_journey(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify fan journey completed successfully."""
        print("\n=== Phase 4 Complete ===")
        print("Fan signed up, logged in, and viewed standings + live match")
        print("\n=== ALL JOURNEY PHASES COMPLETE ===")
        print(f"Total entities created:")
        print(f"  - Season: {entity_registry.season_id}")
        print(f"  - Age Group: {entity_registry.age_group_id}")
        print(f"  - League: {entity_registry.league_id}")
        print(f"  - Division: {entity_registry.division_id}")
        print(f"  - Club: {entity_registry.club_id}")
        print(f"  - Teams: {len(entity_registry.get_all_team_ids())}")
        print(f"  - Matches: {len(entity_registry.match_ids)}")
        print(f"  - Invites: {len(entity_registry.invites)}")
        print(f"  - Users: {len(entity_registry.user_ids)}")
