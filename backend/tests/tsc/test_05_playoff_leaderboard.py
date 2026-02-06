"""
TSC Journey Tests - Phase 5: Playoff Goals Leaderboard.

This phase tests the playoff goals leaderboard feature:
- Admin creates a playoff match (match_type_id=4)
- Admin live-scores the match with player goals
- Fan verifies the goals leaderboard filters by match type

Depends on Phase 0 (admin setup) and Phase 2 (roster creation).

Run: pytest tests/tsc/test_05_playoff_leaderboard.py -v
"""


from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig

PLAYOFF_MATCH_TYPE_ID = 4


class TestPlayoffGoalsLeaderboard:
    """Phase 5: Playoff match live-scoring and leaderboard verification."""

    # === Setup: Admin creates and live-scores a playoff match ===

    def test_01_login_admin(
        self,
        tsc_client: TSCClient,
        existing_admin_credentials: tuple[str, str],
    ):
        """Login as admin to create playoff match."""
        username, password = existing_admin_credentials
        result = tsc_client.login(username, password)

        assert "access_token" in result or "session" in result
        print(f"Logged in as admin: {username}")

    def test_02_complete_live_league_match(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Complete the league match left in LIVE status by Phase 2."""
        assert len(entity_registry.match_ids) > 0, "Matches required (run Phase 2)"

        live_match_id = entity_registry.match_ids[-1]
        result = tsc_client.update_match_score(
            match_id=live_match_id,
            home_score=2,
            away_score=1,
            match_status="completed",
        )

        assert result is not None
        print(f"Completed league match (ID: {live_match_id}): 2-1")

    def test_03_create_playoff_match(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Create a playoff match (match_type_id=4) between premier and reserve teams."""
        assert entity_registry.premier_team_id, "Premier team required (run Phase 0)"
        assert entity_registry.reserve_team_id, "Reserve team required (run Phase 0)"

        result = tsc_client.create_match(
            home_team_id=entity_registry.premier_team_id,
            away_team_id=entity_registry.reserve_team_id,
            game_date="2025-04-01",
            match_type_id=PLAYOFF_MATCH_TYPE_ID,
        )

        assert "id" in result
        # Store playoff match ID for subsequent tests
        entity_registry.playoff_match_id = result["id"]
        print(f"Created playoff match (ID: {result['id']})")

    def test_04_set_playoff_match_live(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Set the playoff match to LIVE status."""
        match_id = entity_registry.playoff_match_id
        assert match_id, "Playoff match required (run test_03)"

        result = tsc_client.set_match_live(match_id)

        assert result is not None
        print(f"Set playoff match (ID: {match_id}) to LIVE")

    def test_05_record_playoff_goals(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Live-score the playoff match: record goals for roster players."""
        match_id = entity_registry.playoff_match_id
        assert match_id, "Playoff match required"
        assert len(entity_registry.roster_entries) >= 3, "Roster required (run Phase 2)"

        team_id = entity_registry.premier_team_id

        # Player 1 scores twice
        player_1 = entity_registry.roster_entries[0]
        for i in range(2):
            result = tsc_client.post_goal_with_player(
                match_id=match_id,
                team_id=team_id,
                player_id=player_1["id"],
                message=f"Playoff goal {i + 1} from #{player_1['jersey_number']}!",
            )
            assert result is not None

        # Player 2 scores once
        player_2 = entity_registry.roster_entries[1]
        result = tsc_client.post_goal_with_player(
            match_id=match_id,
            team_id=team_id,
            player_id=player_2["id"],
            message=f"Playoff goal from #{player_2['jersey_number']}!",
        )
        assert result is not None

        print(
            f"Recorded 3 playoff goals: "
            f"#{player_1['jersey_number']} x2, #{player_2['jersey_number']} x1"
        )

    def test_06_complete_playoff_match(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Complete the playoff match."""
        match_id = entity_registry.playoff_match_id
        assert match_id, "Playoff match required"

        result = tsc_client.update_match_score(
            match_id=match_id,
            home_score=3,
            away_score=0,
            match_status="completed",
        )

        assert result is not None
        print(f"Completed playoff match (ID: {match_id}): 3-0")

    # === Verification: Fan checks the leaderboard ===

    def test_07_login_fan(
        self,
        tsc_client: TSCClient,
        tsc_config: TSCConfig,
    ):
        """Login as fan to view leaderboard."""
        result = tsc_client.login_club_fan()

        assert "access_token" in result or "session" in result
        print(f"Logged in as club fan: {tsc_config.full_club_fan_username}")

    def test_08_verify_unfiltered_leaderboard_includes_playoff_goals(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify the unfiltered leaderboard includes playoff goals."""
        leaderboard = tsc_client.get_goals_leaderboard(
            season_id=entity_registry.season_id,
        )

        assert isinstance(leaderboard, list)
        assert len(leaderboard) > 0, "Leaderboard should have scorers"

        # Find our playoff scorer (player 1 with 2 goals)
        player_1_id = entity_registry.roster_entries[0]["id"]
        scorer = next((p for p in leaderboard if p["player_id"] == player_1_id), None)
        assert scorer is not None, f"Player {player_1_id} should appear in unfiltered leaderboard"
        # Player 1 may have goals from Phase 2 (league match) + Phase 5 (playoff)
        assert scorer["goals"] >= 2, f"Expected at least 2 goals, got {scorer['goals']}"

        print(f"Unfiltered leaderboard: {len(leaderboard)} scorers")
        for p in leaderboard[:5]:
            print(f"  #{p.get('jersey_number')} {p.get('first_name')} {p.get('last_name')}: {p['goals']} goals")

    def test_09_verify_playoff_only_leaderboard(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify the leaderboard filtered by match_type_id=4 shows only playoff goals."""
        leaderboard = tsc_client.get_goals_leaderboard(
            season_id=entity_registry.season_id,
            match_type_id=PLAYOFF_MATCH_TYPE_ID,
        )

        assert isinstance(leaderboard, list)
        assert len(leaderboard) > 0, "Playoff leaderboard should have scorers"

        # Player 1 should have exactly 2 playoff goals
        player_1_id = entity_registry.roster_entries[0]["id"]
        scorer_1 = next((p for p in leaderboard if p["player_id"] == player_1_id), None)
        assert scorer_1 is not None, "Player 1 should appear in playoff leaderboard"
        assert scorer_1["goals"] == 2, f"Player 1 should have 2 playoff goals, got {scorer_1['goals']}"
        assert scorer_1["rank"] == 1, f"Player 1 should be ranked #1, got {scorer_1['rank']}"

        # Player 2 should have exactly 1 playoff goal
        player_2_id = entity_registry.roster_entries[1]["id"]
        scorer_2 = next((p for p in leaderboard if p["player_id"] == player_2_id), None)
        assert scorer_2 is not None, "Player 2 should appear in playoff leaderboard"
        assert scorer_2["goals"] == 1, f"Player 2 should have 1 playoff goal, got {scorer_2['goals']}"

        print(f"Playoff-only leaderboard: {len(leaderboard)} scorers")
        for p in leaderboard:
            print(
                f"  #{p['rank']} #{p.get('jersey_number')} "
                f"{p.get('first_name')} {p.get('last_name')}: "
                f"{p['goals']} goals ({p.get('goals_per_game')} per game)"
            )

    def test_10_verify_league_only_leaderboard_excludes_playoff_goals(
        self,
        tsc_client: TSCClient,
        entity_registry: EntityRegistry,
    ):
        """Verify the league-only leaderboard excludes playoff goals."""
        league_match_type_id = 1

        leaderboard = tsc_client.get_goals_leaderboard(
            season_id=entity_registry.season_id,
            match_type_id=league_match_type_id,
        )

        assert isinstance(leaderboard, list)

        # Player 2 should NOT appear in league leaderboard
        # (they only scored in the playoff match)
        player_2_id = entity_registry.roster_entries[1]["id"]
        scorer_2 = next((p for p in leaderboard if p["player_id"] == player_2_id), None)
        assert scorer_2 is None, "Player 2 should NOT appear in league-only leaderboard"

        print(f"League-only leaderboard: {len(leaderboard)} scorers (correctly excludes playoff-only scorers)")

    def test_11_verify_phase_complete(
        self,
        entity_registry: EntityRegistry,
    ):
        """Verify playoff leaderboard journey completed successfully."""
        assert entity_registry.playoff_match_id is not None, "Playoff match not created"

        print("\n=== Phase 5 Complete ===")
        print("Playoff goals leaderboard verified:")
        print(f"  Playoff match ID: {entity_registry.playoff_match_id}")
        print("  - Unfiltered leaderboard includes playoff + league goals")
        print("  - match_type_id=4 filter shows only playoff goals")
        print("  - match_type_id=1 filter excludes playoff goals")
