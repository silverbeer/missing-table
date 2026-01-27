"""
TSC Journey Tests - Phase 0: Admin Setup.

This phase creates all the infrastructure needed for the test journey:
- Season, age group, league, division
- Club and teams (premier, reserve)
- TSC admin user
- Matches (2 completed)
- Invite for club manager

Run: pytest tests/tsc/test_00_admin_setup.py -v
"""


from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


class TestAdminSetup:
    """Phase 0: Admin creates infrastructure and invites club manager."""

    def test_00_reset_registry(self, entity_registry: EntityRegistry):
        """Reset accumulated registry data for fresh test run."""
        entity_registry.reset_for_new_run()

    def test_01_login_existing_admin(
        self,
        tsc_client: TSCClient,
        existing_admin_credentials: tuple[str, str],
    ):
        """Login as existing admin to create infrastructure."""
        username, password = existing_admin_credentials
        result = tsc_client.login(username, password)

        assert "access_token" in result or "session" in result
        print(f"Logged in as existing admin: {username}")

    def test_02_create_season(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create test season."""
        result = tsc_client.create_season()

        assert "id" in result
        assert result["name"] == tsc_config.full_season_name
        print(f"Created season: {result['name']} (ID: {result['id']})")

    def test_03_create_age_group(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create test age group."""
        result = tsc_client.create_age_group()

        assert "id" in result
        assert result["name"] == tsc_config.full_age_group_name
        print(f"Created age group: {result['name']} (ID: {result['id']})")

    def test_04_create_league(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create test league (required for division)."""
        result = tsc_client.create_league()

        assert "id" in result
        print(f"Created league: {result['name']} (ID: {result['id']})")

    def test_05_create_division(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create test division."""
        result = tsc_client.create_division()

        assert "id" in result
        assert result["name"] == tsc_config.full_division_name
        print(f"Created division: {result['name']} (ID: {result['id']})")

    def test_06_create_club(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create test club."""
        result = tsc_client.create_club()

        assert "id" in result
        assert result["name"] == tsc_config.full_club_name
        print(f"Created club: {result['name']} (ID: {result['id']})")

    def test_07_create_tsc_admin_user(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
        existing_admin_credentials: tuple[str, str],
    ):
        """Create TSC admin user via signup (idempotent - handles existing users)."""
        # Note: Signup creates a regular user, not admin
        # Admin role needs to be assigned separately or via invite
        # For now, we'll create the user and use the existing admin for admin operations

        # Create TSC admin user (handle if already exists)
        try:
            result = tsc_client.client.signup(
                username=tsc_config.full_admin_username,
                password=tsc_config.admin_password,
                display_name=f"TSC Admin ({tsc_config.prefix})",
            )
            assert "user_id" in result or "user" in result or "id" in result
            print(f"Created TSC admin user: {tsc_config.full_admin_username}")
        except Exception as e:
            error_str = str(e).lower()
            if "already" in error_str or "taken" in error_str or "exists" in error_str:
                print(f"TSC admin user already exists: {tsc_config.full_admin_username}")
            else:
                raise

        # Re-login as existing admin to continue setup
        username, password = existing_admin_credentials
        tsc_client.login(username, password)

    def test_08_create_premier_team(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create premier team."""
        result = tsc_client.create_premier_team()

        assert "id" in result
        assert result["name"] == tsc_config.full_premier_team_name
        print(f"Created premier team: {result['name']} (ID: {result['id']})")

    def test_09_create_reserve_team(self, tsc_client: TSCClient, tsc_config: TSCConfig):
        """Create reserve team."""
        result = tsc_client.create_reserve_team()

        assert "id" in result
        assert result["name"] == tsc_config.full_reserve_team_name
        print(f"Created reserve team: {result['name']} (ID: {result['id']})")

    def test_10_create_match_1(self, tsc_client: TSCClient, entity_registry: EntityRegistry):
        """Create first match (Premier vs Reserve)."""
        result = tsc_client.create_match(
            home_team_id=entity_registry.premier_team_id,
            away_team_id=entity_registry.reserve_team_id,
            game_date="2025-02-01",
            home_score=0,
            away_score=0,
            status="scheduled",
        )

        assert "id" in result
        print(f"Created match 1: Premier vs Reserve (ID: {result['id']})")

    def test_11_create_match_2(self, tsc_client: TSCClient, entity_registry: EntityRegistry):
        """Create second match (Reserve vs Premier)."""
        result = tsc_client.create_match(
            home_team_id=entity_registry.reserve_team_id,
            away_team_id=entity_registry.premier_team_id,
            game_date="2025-02-08",
            home_score=0,
            away_score=0,
            status="scheduled",
        )

        assert "id" in result
        print(f"Created match 2: Reserve vs Premier (ID: {result['id']})")

    def test_12_update_match_scores(self, tsc_client: TSCClient, entity_registry: EntityRegistry):
        """Update scores for both matches."""
        # Update match 1: 2-1
        result1 = tsc_client.update_match_score(
            match_id=entity_registry.match_ids[0],
            home_score=2,
            away_score=1,
            match_status="completed",
        )
        assert result1.get("home_score") == 2 or "id" in result1

        # Update match 2: 0-3
        result2 = tsc_client.update_match_score(
            match_id=entity_registry.match_ids[1],
            home_score=0,
            away_score=3,
            match_status="completed",
        )
        assert result2.get("away_score") == 3 or "id" in result2

        print("Updated match scores: Match 1 (2-1), Match 2 (0-3)")

    def test_13_create_club_manager_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create invite for club manager."""
        result = tsc_client.create_club_manager_invite()

        assert "invite_code" in result
        assert len(result["invite_code"]) == 12
        print(f"Created club manager invite: {result['invite_code']}")

    def test_14_create_team_manager_invite(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create invite for team manager (admin creates since club manager can't)."""
        result = tsc_client.create_team_manager_invite(
            team_id=entity_registry.premier_team_id
        )

        assert "invite_code" in result
        assert len(result["invite_code"]) == 12
        print(f"Created team manager invite: {result['invite_code']}")

    def test_15_verify_setup(self, tsc_client: TSCClient, entity_registry: EntityRegistry):
        """Verify all entities were created correctly."""
        assert entity_registry.season_id is not None, "Season not created"
        assert entity_registry.age_group_id is not None, "Age group not created"
        assert entity_registry.league_id is not None, "League not created"
        assert entity_registry.division_id is not None, "Division not created"
        assert entity_registry.club_id is not None, "Club not created"
        assert entity_registry.premier_team_id is not None, "Premier team not created"
        assert entity_registry.reserve_team_id is not None, "Reserve team not created"
        assert len(entity_registry.match_ids) >= 2, "Matches not created"
        assert len(entity_registry.invites) >= 2, "Invites not created"

        print("\n=== Phase 0 Complete ===")
        print(f"Season ID: {entity_registry.season_id}")
        print(f"Age Group ID: {entity_registry.age_group_id}")
        print(f"League ID: {entity_registry.league_id}")
        print(f"Division ID: {entity_registry.division_id}")
        print(f"Club ID: {entity_registry.club_id}")
        print(f"Premier Team ID: {entity_registry.premier_team_id}")
        print(f"Reserve Team ID: {entity_registry.reserve_team_id}")
        print(f"Match IDs: {entity_registry.match_ids}")
        print(f"Invites: {len(entity_registry.invites)}")
