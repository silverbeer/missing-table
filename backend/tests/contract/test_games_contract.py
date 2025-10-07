"""Contract tests for games endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient, NotFoundError
from api_client.models import EnhancedGame, GamePatch


@pytest.mark.contract
class TestGamesReadContract:
    """Test read operations for games endpoints."""

    def test_get_games_returns_list(self, api_client: MissingTableClient):
        """Test getting all games returns a list."""
        games = api_client.get_games()

        assert isinstance(games, list)

    def test_get_games_with_filters(self, api_client: MissingTableClient):
        """Test getting games with various filters."""
        # Test with season filter
        games = api_client.get_games(season_id=1)
        assert isinstance(games, list)

        # Test with age group filter
        games = api_client.get_games(age_group_id=1)
        assert isinstance(games, list)

        # Test with game type filter
        games = api_client.get_games(game_type_id=1)
        assert isinstance(games, list)

        # Test with limit
        games = api_client.get_games(limit=5)
        assert isinstance(games, list)

        # Test with upcoming filter
        games = api_client.get_games(upcoming=True)
        assert isinstance(games, list)

    def test_get_games_by_team(self, api_client: MissingTableClient):
        """Test getting games for a specific team."""
        # Use team_id=1 (should exist in test data)
        games = api_client.get_games_by_team(team_id=1)

        assert isinstance(games, list)

    def test_get_nonexistent_game(self, api_client: MissingTableClient):
        """Test getting a non-existent game returns 404."""
        with pytest.raises(NotFoundError) as exc_info:
            api_client.get_game(game_id=999999)

        assert exc_info.value.status_code == 404


@pytest.mark.contract
class TestGamesWriteContract:
    """Test write operations for games endpoints."""

    def test_create_game(self, authenticated_api_client: MissingTableClient):
        """Test creating a new game."""
        game = EnhancedGame(
            game_date="2025-12-15",
            home_team_id=1,
            away_team_id=2,
            home_score=0,
            away_score=0,
            season_id=1,
            age_group_id=1,
            game_type_id=1,
            status="scheduled",
        )

        try:
            response = authenticated_api_client.create_game(game)
            assert "id" in response or response is not None
        except AuthorizationError:
            # User may not have permission
            pytest.skip("User does not have permission to create games")

    def test_update_game_full(self, authenticated_api_client: MissingTableClient):
        """Test full update of a game (PUT)."""
        # First get a game to update
        games = authenticated_api_client.get_games(limit=1)
        if not games:
            pytest.skip("No games available to test update")

        game_id = games[0]["id"]

        # Create updated game data
        updated_game = EnhancedGame(
            game_date=games[0]["game_date"],
            home_team_id=games[0]["home_team_id"],
            away_team_id=games[0]["away_team_id"],
            home_score=3,
            away_score=2,
            season_id=games[0]["season_id"],
            age_group_id=games[0]["age_group_id"],
            game_type_id=games[0]["game_type_id"],
            status="played",
        )

        try:
            response = authenticated_api_client.update_game(game_id, updated_game)
            assert response is not None
        except AuthorizationError:
            pytest.skip("User does not have permission to update games")

    def test_patch_game_partial_update(self, authenticated_api_client: MissingTableClient):
        """Test partial update of a game (PATCH)."""
        # Get a game to patch
        games = authenticated_api_client.get_games(limit=1)
        if not games:
            pytest.skip("No games available to test patch")

        game_id = games[0]["id"]

        # Create patch with only score updates
        patch = GamePatch(
            home_score=4,
            away_score=3,
            status="played",
        )

        try:
            response = authenticated_api_client.patch_game(game_id, patch)

            # Verify response contains updated data
            assert response is not None

            # Verify the game was actually updated
            updated_game = authenticated_api_client.get_game(game_id)
            assert updated_game["home_score"] == 4
            assert updated_game["away_score"] == 3
            assert updated_game["status"] == "played" or updated_game.get("match_status") == "played"

        except AuthorizationError:
            pytest.skip("User does not have permission to patch games")

    def test_patch_game_auto_status_update(self, authenticated_api_client: MissingTableClient):
        """Test that updating scores automatically sets status to played."""
        games = authenticated_api_client.get_games(limit=1)
        if not games:
            pytest.skip("No games available")

        game_id = games[0]["id"]

        # Patch with scores but no explicit status
        patch = GamePatch(
            home_score=2,
            away_score=1,
        )

        try:
            authenticated_api_client.patch_game(game_id, patch)

            # Verify status was auto-set to played
            updated_game = authenticated_api_client.get_game(game_id)

            # Status should be "played" when scores are set
            # (This tests the business logic requirement)
            assert updated_game.get("status") == "played" or updated_game.get("match_status") == "played"

        except AuthorizationError:
            pytest.skip("User does not have permission to patch games")

    def test_patch_game_validation(self, authenticated_api_client: MissingTableClient):
        """Test that patch validates score values."""
        games = authenticated_api_client.get_games(limit=1)
        if not games:
            pytest.skip("No games available")

        game_id = games[0]["id"]

        # Try to patch with invalid scores (negative)
        from api_client import ValidationError

        patch = GamePatch(
            home_score=-1,  # Invalid
            away_score=2,
        )

        try:
            with pytest.raises(ValidationError):
                authenticated_api_client.patch_game(game_id, patch)
        except AuthorizationError:
            pytest.skip("User does not have permission to patch games")


@pytest.mark.contract
class TestGamesBusinessLogic:
    """Test business logic for games."""

    def test_game_status_values(self, api_client: MissingTableClient):
        """Test that games have valid status values."""
        games = api_client.get_games(limit=10)

        valid_statuses = ["scheduled", "played", "postponed", "cancelled", "completed"]

        for game in games:
            status = game.get("status") or game.get("match_status")
            if status:
                assert status in valid_statuses, f"Invalid status: {status}"

    def test_game_scores_non_negative(self, api_client: MissingTableClient):
        """Test that game scores are non-negative."""
        games = api_client.get_games(limit=20)

        for game in games:
            if game.get("home_score") is not None:
                assert game["home_score"] >= 0
            if game.get("away_score") is not None:
                assert game["away_score"] >= 0

    def test_game_has_different_teams(self, api_client: MissingTableClient):
        """Test that home and away teams are different."""
        games = api_client.get_games(limit=20)

        for game in games:
            if "home_team_id" in game and "away_team_id" in game:
                assert game["home_team_id"] != game["away_team_id"], \
                    f"Game {game.get('id')} has same home and away team"
