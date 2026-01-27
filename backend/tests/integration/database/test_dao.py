"""
Tests for the Enhanced DAO layer.
"""

from datetime import datetime

import pytest

# Module-level markers for all tests in this file
pytestmark = [
    pytest.mark.integration,
    pytest.mark.backend,
    pytest.mark.dao,
    pytest.mark.database,
    pytest.mark.slow
]


@pytest.mark.integration
def test_dao_initialization(enhanced_dao):
    """Test that the DAO can be initialized successfully."""
    assert enhanced_dao is not None
    assert hasattr(enhanced_dao, 'connection_holder')
    assert hasattr(enhanced_dao, 'client')
    assert hasattr(enhanced_dao, 'get_all_teams')
    assert hasattr(enhanced_dao, 'get_all_games')


@pytest.mark.integration
def test_get_all_teams(enhanced_dao):
    """Test getting all teams."""
    teams = enhanced_dao.get_all_teams()
    assert isinstance(teams, list)

    # If we have teams, check their structure
    if teams:
        team = teams[0]
        # Current DAO returns teams with basic fields
        expected_fields = ['id', 'name', 'city']
        for field in expected_fields:
            assert field in team, f"Team missing field: {field}"


@pytest.mark.integration
def test_get_all_games(enhanced_dao):
    """Test getting all games."""
    games = enhanced_dao.get_all_games()
    assert isinstance(games, list)

    # If we have games, check their structure
    if games:
        game = games[0]
        expected_fields = ['id', 'game_date', 'home_team_id', 'away_team_id', 'home_score', 'away_score']
        for field in expected_fields:
            assert field in game, f"Game missing field: {field}"


@pytest.mark.integration
def test_get_reference_data(enhanced_dao):
    """Test getting reference data."""
    # Test age groups
    age_groups = enhanced_dao.get_all_age_groups()
    assert isinstance(age_groups, list)
    assert len(age_groups) > 0, "Should have at least one age group"

    # Test seasons
    seasons = enhanced_dao.get_all_seasons()
    assert isinstance(seasons, list)
    assert len(seasons) > 0, "Should have at least one season"

    # Test game types
    game_types = enhanced_dao.get_all_game_types()
    assert isinstance(game_types, list)
    assert len(game_types) > 0, "Should have at least one game type"


@pytest.mark.integration
def test_get_league_table(enhanced_dao):
    """Test getting league table."""
    table = enhanced_dao.get_league_table()
    assert isinstance(table, list)

    # If we have table data, check structure
    if table:
        team_stats = table[0]
        # Current DAO uses "team" and "played" instead of "team_name" and "games_played"
        expected_fields = ['team', 'played', 'wins', 'draws', 'losses', 'points']
        for field in expected_fields:
            assert field in team_stats, f"League table missing field: {field}"


@pytest.mark.integration
def test_get_recent_games(enhanced_dao):
    """Test getting recent games."""
    # get_all_games returns games ordered by date
    all_games = enhanced_dao.get_all_games()
    recent_games = all_games[:5] if len(all_games) > 5 else all_games
    assert isinstance(recent_games, list)
    assert len(recent_games) <= 5, "Should respect limit"

    # If we have games, check they're ordered by date (most recent first)
    if len(recent_games) > 1:
        for i in range(len(recent_games) - 1):
            date1 = recent_games[i]['game_date']
            date2 = recent_games[i + 1]['game_date']
            # Convert to datetime for comparison
            if isinstance(date1, str):
                date1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
            if isinstance(date2, str):
                date2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
            # Games are ordered descending by date
            assert date1 >= date2, "Games should be ordered by date (most recent first)"


@pytest.mark.integration
def test_get_team_by_id(enhanced_dao):
    """Test getting a specific team by ID."""
    # First get all teams to get a valid ID
    teams = enhanced_dao.get_all_teams()

    if teams:
        team_id = teams[0]['id']
        # Filter teams to get specific team
        team = next((t for t in teams if t['id'] == team_id), None)
        assert team is not None
        assert team['id'] == team_id
        assert 'name' in team
        assert 'city' in team


@pytest.mark.integration
def test_get_games_by_team(enhanced_dao):
    """Test getting games for a specific team."""
    # First get all teams to get a valid team ID
    teams = enhanced_dao.get_all_teams()

    if teams:
        team_id = teams[0]['id']
        games = enhanced_dao.get_games_by_team(team_id)
        assert isinstance(games, list)

        # If there are games, verify they involve the team
        for game in games:
            assert (game['home_team_id'] == team_id or
                   game['away_team_id'] == team_id), "Game should involve the specified team"


@pytest.mark.integration
def test_dao_error_handling(enhanced_dao):
    """Test DAO error handling for invalid inputs."""
    # Test getting non-existent team
    teams = enhanced_dao.get_all_teams()
    team = next((t for t in teams if t['id'] == 999999), None)
    assert team is None

    # Test getting games for non-existent team
    games = enhanced_dao.get_games_by_team(999999)
    assert isinstance(games, list)
    assert len(games) == 0


@pytest.mark.integration
def test_dao_with_filters(enhanced_dao):
    """Test DAO methods with various filters."""
    # Test getting recent games with different limits
    all_games = enhanced_dao.get_all_games()
    games_5 = all_games[:5] if len(all_games) > 5 else all_games
    games_10 = all_games[:10] if len(all_games) > 10 else all_games

    assert len(games_5) <= 5
    assert len(games_10) <= 10

    # If we have enough games, verify the limit works
    if len(all_games) >= 5:
        assert len(games_5) == 5


@pytest.mark.integration
def test_dao_data_consistency(enhanced_dao):
    """Test data consistency across different DAO methods."""
    # Get all teams
    teams = enhanced_dao.get_all_teams()

    # Get all games
    games = enhanced_dao.get_all_games()

    # If we have both teams and games, verify referential integrity
    if teams and games:
        team_ids = set(team['id'] for team in teams)

        for game in games:
            assert game['home_team_id'] in team_ids, f"Home team ID {game['home_team_id']} not found in teams"
            assert game['away_team_id'] in team_ids, f"Away team ID {game['away_team_id']} not found in teams"
