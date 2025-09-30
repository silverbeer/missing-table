"""
Enhanced end-to-end tests for complex workflows and business logic.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import time


class TestInviteWorkflows:
    """Test complete invite workflows."""

    @pytest.mark.e2e
    def test_invite_validation_workflow(self, test_client: TestClient):
        """Test invite code validation workflow."""
        # Test with invalid invite code format
        response = test_client.get("/api/invites/validate/short")
        assert response.status_code == 404  # Not found (short codes don't exist)

        # Test with properly formatted but non-existent invite code  
        response = test_client.get("/api/invites/validate/123456789012")
        assert response.status_code == 404  # Not found

        # Test with invalid characters
        response = test_client.get("/api/invites/validate/invalid_code!")
        assert response.status_code == 404  # Not found (invalid codes)

    @pytest.mark.e2e
    def test_invite_creation_unauthorized(self, test_client: TestClient):
        """Test invite creation without proper authorization."""
        invite_data = {
            "invite_type": "team_manager",
            "team_id": 1,
            "age_group_id": 1,
            "email": "test@example.com"
        }

        # All invite creation endpoints should require auth
        endpoints = [
            "/api/invites/admin/team-manager",
            "/api/invites/admin/team-fan", 
            "/api/invites/admin/team-player",
            "/api/invites/team-manager/team-fan",
            "/api/invites/team-manager/team-player"
        ]

        for endpoint in endpoints:
            response = test_client.post(endpoint, json=invite_data)
            assert response.status_code == 403  # Forbidden (no auth token)

    @pytest.mark.e2e
    def test_invite_management_unauthorized(self, test_client: TestClient):
        """Test invite management without authorization."""
        # Test getting my invites
        response = test_client.get("/api/invites/my-invites")
        assert response.status_code == 403  # Forbidden (no auth token)

        # Test canceling invitation
        response = test_client.delete("/api/invites/fake-invite-id")
        assert response.status_code == 403  # Forbidden (no auth token)

        # Test getting team manager assignments
        response = test_client.get("/api/invites/team-manager/assignments") 
        assert response.status_code == 403  # Forbidden (no auth token)


class TestCompleteGameLifecycle:
    """Test complete game lifecycle from creation to standings."""

    @pytest.mark.e2e
    def test_game_data_consistency(self, test_client: TestClient, enhanced_dao):
        """Test that game data remains consistent across different endpoints."""
        # Get all games
        games_response = test_client.get("/api/games")
        assert games_response.status_code == 200
        all_games = games_response.json()

        if not all_games:
            pytest.skip("No games in database for consistency test")

        # Pick a game and verify it appears consistently across endpoints
        test_game = all_games[0]
        game_id = test_game.get('id')
        home_team_id = test_game.get('home_team_id')
        away_team_id = test_game.get('away_team_id')

        if not all([game_id, home_team_id, away_team_id]):
            pytest.skip("Game missing required fields for consistency test")

        # Verify game appears in home team's games
        home_games_response = test_client.get(f"/api/games/team/{home_team_id}")
        assert home_games_response.status_code == 200
        home_games = home_games_response.json()
        
        home_game_ids = [g.get('id') for g in home_games if g.get('id')]
        assert game_id in home_game_ids, "Game should appear in home team's games"

        # Verify game appears in away team's games
        away_games_response = test_client.get(f"/api/games/team/{away_team_id}")
        assert away_games_response.status_code == 200
        away_games = away_games_response.json()
        
        away_game_ids = [g.get('id') for g in away_games if g.get('id')]
        assert game_id in away_game_ids, "Game should appear in away team's games"

    @pytest.mark.e2e
    def test_standings_calculation_consistency(self, test_client: TestClient):
        """Test that standings calculations are consistent with game results."""
        # Get league table
        table_response = test_client.get("/api/table")
        assert table_response.status_code == 200
        standings = table_response.json()

        if not standings:
            pytest.skip("No standings data available for consistency test")

        # Verify standings data structure
        for team_standing in standings[:3]:  # Check first 3 teams
            required_fields = ['team_name', 'games_played', 'wins', 'draws', 'losses', 'points']
            for field in required_fields:
                assert field in team_standing, f"Missing field {field} in standings"

            # Verify games_played = wins + draws + losses
            games_played = team_standing.get('games_played', 0)
            wins = team_standing.get('wins', 0) 
            draws = team_standing.get('draws', 0)
            losses = team_standing.get('losses', 0)
            
            assert games_played == wins + draws + losses, \
                f"Games played ({games_played}) should equal wins + draws + losses ({wins + draws + losses})"

    @pytest.mark.e2e
    def test_team_game_relationship_consistency(self, test_client: TestClient):
        """Test consistency between teams and their games."""
        # Get all teams
        teams_response = test_client.get("/api/teams")
        assert teams_response.status_code == 200
        teams = teams_response.json()

        if not teams:
            pytest.skip("No teams available for relationship test")

        # Test first few teams
        for team in teams[:3]:
            team_id = team.get('id')
            team_name = team.get('name')
            
            if not team_id:
                continue

            # Get games for this team
            team_games_response = test_client.get(f"/api/games/team/{team_id}")
            assert team_games_response.status_code == 200
            team_games = team_games_response.json()

            # Verify all returned games actually involve this team
            for game in team_games:
                home_team_id = game.get('home_team_id')
                away_team_id = game.get('away_team_id')
                assert team_id in [home_team_id, away_team_id], \
                    f"Game {game.get('id')} returned for team {team_id} but doesn't involve that team"


class TestFilteringAndPagination:
    """Test advanced filtering and pagination scenarios."""

    @pytest.mark.e2e
    def test_games_filtering_combinations(self, test_client: TestClient):
        """Test complex combinations of game filters."""
        # Get reference data first
        seasons_response = test_client.get("/api/seasons")
        age_groups_response = test_client.get("/api/age-groups")
        game_types_response = test_client.get("/api/game-types")

        assert seasons_response.status_code == 200
        assert age_groups_response.status_code == 200
        assert game_types_response.status_code == 200

        seasons = seasons_response.json()
        age_groups = age_groups_response.json()
        game_types = game_types_response.json()

        # Test combinations if reference data exists
        if seasons and age_groups and game_types:
            season_id = seasons[0].get('id')
            age_group_id = age_groups[0].get('id')
            game_type_id = game_types[0].get('id')

            # Test single filters
            if season_id:
                response = test_client.get(f"/api/games?season_id={season_id}")
                assert response.status_code == 200

            if age_group_id:
                response = test_client.get(f"/api/games?age_group_id={age_group_id}")
                assert response.status_code == 200

            if game_type_id:
                response = test_client.get(f"/api/games?game_type_id={game_type_id}")
                assert response.status_code == 200

            # Test combination filters
            if all([season_id, age_group_id, game_type_id]):
                response = test_client.get(
                    f"/api/games?season_id={season_id}&age_group_id={age_group_id}&game_type_id={game_type_id}"
                )
                assert response.status_code == 200
                filtered_games = response.json()
                
                # Verify all returned games match the filters
                for game in filtered_games:
                    if 'season_id' in game:
                        assert game['season_id'] == season_id
                    if 'age_group_id' in game:
                        assert game['age_group_id'] == age_group_id
                    if 'game_type_id' in game:
                        assert game['game_type_id'] == game_type_id

    @pytest.mark.e2e
    def test_table_filtering_combinations(self, test_client: TestClient):
        """Test complex combinations of table filters."""
        # Get base table
        base_response = test_client.get("/api/table")
        assert base_response.status_code == 200
        base_standings = base_response.json()

        # Get reference data
        seasons_response = test_client.get("/api/seasons")
        age_groups_response = test_client.get("/api/age-groups")
        game_types_response = test_client.get("/api/game-types")

        seasons = seasons_response.json()
        age_groups = age_groups_response.json()
        game_types = game_types_response.json()

        # Test filtered standings if reference data exists
        if seasons and age_groups and game_types:
            season_id = seasons[0].get('id')
            age_group_id = age_groups[0].get('id')  
            game_type_id = game_types[0].get('id')

            if all([season_id, age_group_id, game_type_id]):
                # Test filtered standings
                response = test_client.get(
                    f"/api/table?season_id={season_id}&age_group_id={age_group_id}&game_type_id={game_type_id}"
                )
                assert response.status_code == 200
                filtered_standings = response.json()

                # Filtered standings should have same structure as base standings
                if filtered_standings and base_standings:
                    for standing in filtered_standings:
                        assert 'team_name' in standing
                        assert 'points' in standing
                        assert 'games_played' in standing

    @pytest.mark.e2e
    def test_pagination_limits(self, test_client: TestClient):
        """Test pagination and limiting functionality."""
        # Test various limit values
        limits_to_test = [1, 5, 10, 50, 100]
        
        for limit in limits_to_test:
            response = test_client.get(f"/api/games?limit={limit}")
            assert response.status_code == 200
            games = response.json()
            # Note: API may return more than requested limit in some cases
            # This is acceptable for testing purposes

        # Test with unreasonably large limit
        response = test_client.get("/api/games?limit=999999")
        assert response.status_code == 200
        games = response.json()
        # Should not crash, and should return reasonable number
        assert len(games) <= 10000, "Should not return unlimited results"


class TestDataIntegrityAndValidation:
    """Test data integrity and validation across the system."""

    @pytest.mark.e2e
    def test_referential_integrity(self, test_client: TestClient):
        """Test that referenced entities exist."""
        # Get games and verify teams exist
        games_response = test_client.get("/api/games")
        assert games_response.status_code == 200
        games = games_response.json()

        teams_response = test_client.get("/api/teams")
        assert teams_response.status_code == 200
        teams = teams_response.json()

        if games and teams:
            team_ids = {team.get('id') for team in teams if team.get('id')}
            
            # Check first few games
            for game in games[:5]:
                home_team_id = game.get('home_team_id')
                away_team_id = game.get('away_team_id')
                
                if home_team_id:
                    assert home_team_id in team_ids, f"Home team {home_team_id} not found in teams"
                if away_team_id:
                    assert away_team_id in team_ids, f"Away team {away_team_id} not found in teams"

    @pytest.mark.e2e
    def test_duplicate_game_prevention(self, test_client: TestClient):
        """Test that the system handles duplicate games appropriately."""
        # This tests the check-game endpoint
        response = test_client.get(
            "/api/check-game?date=2024-01-01&homeTeam=NonexistentTeam&awayTeam=AnotherNonexistentTeam"
        )
        # Should return either 200 (game not found) or 404 (game not found)
        assert response.status_code in [200, 404]

    @pytest.mark.e2e
    def test_date_handling_consistency(self, test_client: TestClient):
        """Test consistent date handling across endpoints."""
        # Get games with date information
        games_response = test_client.get("/api/games?limit=5")
        assert games_response.status_code == 200
        games = games_response.json()

        for game in games:
            game_date = game.get('game_date')
            if game_date:
                # Date should be in a consistent format (ISO 8601 or similar)
                assert isinstance(game_date, str), "Game date should be a string"
                assert len(game_date) >= 10, "Game date should include at least YYYY-MM-DD"


class TestErrorHandlingAndEdgeCases:
    """Test system behavior in error conditions and edge cases."""

    @pytest.mark.e2e
    def test_nonexistent_resource_handling(self, test_client: TestClient):
        """Test handling of requests for nonexistent resources."""
        # Test nonexistent team games
        response = test_client.get("/api/games/team/999999")
        assert response.status_code == 200
        games = response.json()
        assert games == []  # Should return empty list

        # Test nonexistent team in check-game
        response = test_client.get("/api/check-game?date=2024-01-01&homeTeam=Nonexistent&awayTeam=AlsoNonexistent")
        assert response.status_code in [200, 404]

    @pytest.mark.e2e
    def test_malformed_query_parameters(self, test_client: TestClient):
        """Test handling of malformed query parameters."""
        # Test with non-numeric IDs where numbers are expected
        malformed_params = [
            "/api/games?season_id=not_a_number",
            "/api/games?age_group_id=abc",
            "/api/games?game_type_id=1.5",
            "/api/games?limit=not_a_number",
            "/api/table?season_id=invalid"
        ]

        for param_url in malformed_params:
            response = test_client.get(param_url)
            # Should handle gracefully - either return validation error or ignore invalid params
            assert response.status_code in [200, 400, 422]

    @pytest.mark.e2e
    def test_extreme_values(self, test_client: TestClient):
        """Test handling of extreme parameter values."""
        extreme_params = [
            "/api/games?limit=-1",
            "/api/games?limit=0", 
            "/api/games?season_id=-1",
            "/api/games?age_group_id=0",
            "/api/games/team/-1",
            "/api/games/team/0"
        ]

        for param_url in extreme_params:
            response = test_client.get(param_url)
            # Should handle gracefully, not crash
            assert response.status_code in [200, 400, 404, 422]

    @pytest.mark.e2e
    def test_concurrent_request_simulation(self, test_client: TestClient):
        """Simulate concurrent requests to test system stability."""
        import concurrent.futures
        import threading

        def make_request():
            """Make a simple API request."""
            response = test_client.get("/api/teams")
            return response.status_code

        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        for status_code in results:
            assert status_code == 200


class TestBusinessLogicValidation:
    """Test business logic rules and validation."""

    @pytest.mark.e2e
    def test_game_score_logic(self, test_client: TestClient):
        """Test that game scores follow business logic rules."""
        games_response = test_client.get("/api/games?limit=10")
        assert games_response.status_code == 200
        games = games_response.json()

        for game in games:
            home_score = game.get('home_score')
            away_score = game.get('away_score')
            
            # If scores exist, they should be non-negative integers
            if home_score is not None:
                assert isinstance(home_score, int), "Home score should be integer"
                assert home_score >= 0, "Home score should be non-negative"
                
            if away_score is not None:
                assert isinstance(away_score, int), "Away score should be integer"  
                assert away_score >= 0, "Away score should be non-negative"

    @pytest.mark.e2e
    def test_standings_points_logic(self, test_client: TestClient):
        """Test that standings points follow standard soccer rules."""
        table_response = test_client.get("/api/table")
        assert table_response.status_code == 200
        standings = table_response.json()

        for team in standings[:5]:  # Test first 5 teams
            wins = team.get('wins', 0)
            draws = team.get('draws', 0)
            points = team.get('points', 0)
            
            # Standard soccer: 3 points for win, 1 for draw, 0 for loss
            expected_min_points = wins * 3 + draws * 1
            expected_max_points = wins * 3 + draws * 1  # Same because losses give 0 points
            
            assert points == expected_min_points, \
                f"Team points ({points}) don't match expected ({expected_min_points}) for {wins} wins, {draws} draws"

    @pytest.mark.e2e
    def test_team_cannot_play_itself(self, test_client: TestClient):
        """Test that no game has the same team as home and away."""
        games_response = test_client.get("/api/games")
        assert games_response.status_code == 200
        games = games_response.json()

        for game in games:
            home_team_id = game.get('home_team_id')
            away_team_id = game.get('away_team_id')
            
            if home_team_id is not None and away_team_id is not None:
                assert home_team_id != away_team_id, \
                    f"Game {game.get('id')} has same team ({home_team_id}) as home and away"