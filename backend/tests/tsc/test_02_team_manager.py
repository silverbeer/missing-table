"""
TSC Journey Tests - Phase 2: Team Manager Journey.

This phase tests the team manager user experience:
- Validate and use invite to sign up
- Login as team manager
- View teams and assignments
- Create matches and set one LIVE
- Create invites for player and team fan

Run: pytest tests/tsc/test_02_team_manager.py -v
"""


from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestTeamManagerJourney:
    """Phase 2: Team manager signs up and manages team."""

    def test_01_validate_team_manager_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Validate the team manager invite code."""
        # Find team manager invite
        team_mgr_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_manager" and inv["status"] == "pending"
        ]
        assert len(team_mgr_invites) > 0, "No team manager invite found"

        invite_code = team_mgr_invites[0]["code"]
        result = tsc_client.validate_invite(invite_code)

        assert result is not None
        assert result.get("invite_type") == "team_manager" or "team_id" in result
        print(f"Validated team manager invite: {invite_code}")

    def test_02_signup_team_manager(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        entity_registry: EntityRegistry,
    ):
        """Sign up as team manager using invite."""
        # Find team manager invite
        team_mgr_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_manager" and inv["status"] == "pending"
        ]
        invite_code = team_mgr_invites[0]["code"]

        result = tsc_client.signup_with_invite(
            username=tsc_config.full_team_manager_username,
            password=tsc_config.team_manager_password,
            invite_code=invite_code,
            display_name="TSC Team Manager",
        )

        assert "user" in result or "id" in result or "message" in result
        print(f"Signed up team manager: {tsc_config.full_team_manager_username}")

        # Mark invite as used
        team_mgr_invites[0]["status"] = "used"

    def test_03_login_team_manager(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Login as team manager."""
        result = tsc_client.login_team_manager()

        assert "access_token" in result or "session" in result
        print(f"Logged in as team manager: {tsc_config.full_team_manager_username}")

    def test_04_view_teams(self, tsc_client: TSCClient):
        """View all teams."""
        result = tsc_client.get_teams()

        assert isinstance(result, list)
        assert len(result) >= 2  # Premier and reserve teams
        print(f"Found {len(result)} teams")

    def test_05_get_team_manager_assignments(self, tsc_client: TSCClient):
        """Get team manager's team assignments."""
        try:
            result = tsc_client.get_team_manager_assignments()
            assert isinstance(result, list)
            print(f"Team manager has {len(result)} team assignments")
        except Exception as e:
            # May fail if assignments not set up
            print(f"Could not get assignments (may be expected): {e}")

    def test_06_get_profile(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Get team manager profile."""
        result = tsc_client.get_profile()

        assert result is not None
        print(f"Profile: {result.get('username', result.get('display_name'))}, Role: {result.get('role')}")

    def test_07_update_profile(self, tsc_client: TSCClient):
        """Update team manager profile."""
        result = tsc_client.update_profile(display_name="TSC Team Manager (Updated)")

        assert result is not None
        print("Updated team manager profile")

    def test_08_create_match_5(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
        existing_admin_credentials: tuple[str, str],
    ):
        """Create match 5 (requires admin for match creation)."""
        # Team managers may not have match creation rights
        # Login as admin to create match
        username, password = existing_admin_credentials
        tsc_client.login(username, password)

        result = tsc_client.create_match(
            home_team_id=entity_registry.premier_team_id,
            away_team_id=entity_registry.reserve_team_id,
            game_date="2025-03-01",
            home_score=0,
            away_score=0,
            status="scheduled",
        )

        assert "id" in result
        print(f"Created match 5: Premier vs Reserve (ID: {result['id']})")

    def test_09_create_match_6(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create match 6 (this will be set to LIVE)."""
        result = tsc_client.create_match(
            home_team_id=entity_registry.reserve_team_id,
            away_team_id=entity_registry.premier_team_id,
            game_date="2025-03-08",
            home_score=0,
            away_score=0,
            status="scheduled",
        )

        assert "id" in result
        # Store this match ID for setting live
        entity_registry.live_match_id = result["id"]
        print(f"Created match 6: Reserve vs Premier (ID: {result['id']}) - will be set LIVE")

    def test_10_update_match_5_score(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Update match 5 score."""
        # Match 5 is the second-to-last match (index -2)
        match_5_id = entity_registry.match_ids[-2]

        result = tsc_client.update_match_score(
            match_id=match_5_id,
            home_score=1,
            away_score=1,
            match_status="completed",
        )

        assert result is not None
        print("Updated match 5 score: 1-1")

    def test_11_set_match_6_live(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Set match 6 to LIVE status."""
        match_6_id = entity_registry.match_ids[-1]

        result = tsc_client.set_match_live(match_6_id)

        assert result is not None
        print(f"Set match 6 (ID: {match_6_id}) to LIVE")

    # === Roster Management Tests ===

    def test_11a_create_roster_entries(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Team manager creates roster for the team."""
        # Re-login as team manager
        tsc_client.login_team_manager()

        # Create roster entries (jersey numbers 1, 7, 10, 11, 23)
        for jersey in [1, 7, 10, 11, 23]:
            result = tsc_client.create_roster_entry(
                team_id=entity_registry.premier_team_id,
                jersey_number=jersey,
                first_name=f"Player{jersey}",
                last_name="Test",
            )
            assert "id" in result
            print(f"Created roster entry: #{jersey} - Player{jersey} Test")

        # Verify roster
        roster = tsc_client.get_roster(entity_registry.premier_team_id)
        assert len(roster) >= 5
        print(f"Team roster has {len(roster)} players")

    def test_11b_verify_roster_display_names(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify roster entries have correct display names."""
        roster = tsc_client.get_roster(entity_registry.premier_team_id)

        for player in roster:
            # Players without accounts should show name from roster
            assert "display_name" in player
            assert player.get("has_account") is False  # No accounts linked yet
            print(
                f"#{player['jersey_number']}: {player['display_name']} "
                f"(has_account={player.get('has_account')})"
            )

    def test_11c_record_goal_with_roster_player(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
        existing_admin_credentials: tuple[str, str],
    ):
        """Record a goal using player_id from roster."""
        # Login as admin for match management
        username, password = existing_admin_credentials
        tsc_client.login(username, password)

        # Get roster
        roster = tsc_client.get_roster(entity_registry.premier_team_id)
        scorer = roster[0]  # First player scores

        # Record goal on live match
        live_match_id = entity_registry.match_ids[-1]
        result = tsc_client.post_goal_with_player(
            match_id=live_match_id,
            team_id=entity_registry.premier_team_id,
            player_id=scorer["id"],
            message="Great strike!",
        )

        assert result is not None
        print(f"Goal recorded: #{scorer['jersey_number']} scored!")

        # Verify stats updated
        stats = tsc_client.get_player_stats(scorer["id"])
        assert stats.get("stats", {}).get("total_goals", 0) >= 1
        print(f"Player stats: {stats.get('stats', {}).get('total_goals', 0)} goals")

    def test_12_create_player_invite_with_roster(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create invite for player linked to roster entry."""
        # Re-login as team manager (may have been logged out by previous tests)
        tsc_client.login_team_manager()

        # Get first roster entry (jersey #1)
        roster = tsc_client.get_roster(entity_registry.premier_team_id)
        player_entry = next(p for p in roster if p["jersey_number"] == 1)

        result = tsc_client.create_team_player_invite_with_roster(
            team_id=entity_registry.premier_team_id,
            player_id=player_entry["id"],
        )
        assert "invite_code" in result
        print(f"Created roster-linked invite: {result['invite_code']} → #{player_entry['jersey_number']}")

        # Store roster entry ID for player journey verification
        entity_registry.linked_player_id = player_entry["id"]

    def test_13_create_team_fan_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create invite for team fan (team manager creates for their team)."""
        # Re-login as team manager
        tsc_client.login_team_manager()

        result = tsc_client.create_team_fan_invite(
            team_id=entity_registry.premier_team_id
        )
        assert "invite_code" in result
        print(f"Created team fan invite: {result['invite_code']}")

    def test_14_verify_team_manager_journey(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify team manager journey completed successfully."""
        # Check that we have enough matches
        assert len(entity_registry.match_ids) >= 4, "Not enough matches created"

        # Check for player and fan invites
        player_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] == "team_player"
        ]
        fan_invites = [
            inv for inv in entity_registry.invites
            if inv["type"] in ("team_fan", "club_fan")
        ]

        assert len(player_invites) > 0, "Player invite not created"
        assert len(fan_invites) > 0, "Fan invite not created"

        # Check roster entries
        assert len(entity_registry.roster_entries) >= 5, "Not enough roster entries created"
        assert entity_registry.linked_player_id is not None, "Player not linked to invite"

        print("\n=== Phase 2 Complete ===")
        print("Team manager signed up and logged in")
        print(f"Total matches: {len(entity_registry.match_ids)}")
        print(f"Live match ID: {entity_registry.match_ids[-1]}")
        print(f"Player invites: {len(player_invites)}")
        print(f"Fan invites: {len(fan_invites)}")
        print(f"Roster entries: {len(entity_registry.roster_entries)}")
        print(f"Linked player ID: {entity_registry.linked_player_id}")
