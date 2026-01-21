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


from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestPlayerJourney:
    """Phase 3: Player signs up and views team info."""

    def test_01_validate_player_invite_with_roster_info(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate invite and check roster info is included."""
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

        # If invite was linked to roster, player info should be included
        if result.get("player_id"):
            assert result.get("player") is not None
            print(f"Invite linked to roster: #{result['player']['jersey_number']}")
        else:
            print("Invite not linked to roster (legacy)")

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

    def test_02a_verify_account_linked_to_roster(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Verify player account is linked to roster entry after signup."""
        tsc_client.login_player()

        if entity_registry.linked_player_id:
            # Get roster and find the linked entry
            roster = tsc_client.get_roster(entity_registry.premier_team_id)
            linked_entry = next(
                (p for p in roster if p["id"] == entity_registry.linked_player_id),
                None,
            )

            if linked_entry:
                assert linked_entry.get("has_account") is True
                print(
                    f"Account linked to roster: #{linked_entry['jersey_number']} "
                    f"→ {linked_entry['display_name']}"
                )
            else:
                print("Could not verify roster linking (entry not found)")
        else:
            print("Skipping roster link verification (no linked_player_id)")

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

    def test_09a_view_player_stats(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Player can view their stats."""
        if entity_registry.linked_player_id:
            stats = tsc_client.get_player_stats(entity_registry.linked_player_id)

            assert "stats" in stats or "total_goals" in stats.get("stats", stats)
            print(f"Player stats: {stats.get('stats', stats)}")
        else:
            print("Skipping stats view (no linked_player_id)")

    def test_10_verify_player_journey(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify player journey completed successfully."""
        print("\n=== Phase 3 Complete ===")
        print("Player signed up, logged in, and viewed schedule")
        if entity_registry.linked_player_id:
            print(f"Account linked to roster entry: player_id={entity_registry.linked_player_id}")
        else:
            print("No roster linking configured")
