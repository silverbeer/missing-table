import pytest
from backend.dao import data_access


# Path to the test SQLite database
MLSNEXT_DB_FILE = 'mlsnext_u13_fall.db'

def test_get_all_teams():
    db_conn_holder_obj = data_access.DbConnectionHolder(db_file='backend/mlsnext_u13_fall.db')
    dao = data_access.SportsDAO(db_conn_holder_obj)
    teams = dao.get_all_teams()
    assert isinstance(teams, list)  # Check that the result is a list
    if teams:
        assert 'name' in teams[0]  # Check that the 'name' column exists
        assert 'city' in teams[0]  # Check that the 'city' column exists

def test_add_team(data_access):
    data_access.add_team('Test Team', 'Test City')
    teams = data_access.get_all_teams()
    assert 'Test Team' in [team['name'] for team in teams]  # Check that the team was added

def test_get_all_games(data_access):
    games = data_access.get_all_games()
    assert isinstance(games, list)  # Check that the result is a list
    if games:
        assert 'game_date' in games[0]  # Check that the 'game_date' column exists
        assert 'home_team' in games[0]  # Check that the 'home_team' column exists
        assert 'away_team' in games[0]  # Check that the 'away_team' column exists
        assert 'home_score' in games[0]  # Check that the 'home_score' column exists
        assert 'away_score' in games[0]  # Check that the 'away_score' column exists

def test_get_games_by_team(data_access):
    games = data_access.get_games_by_team('Test Team')
    assert isinstance(games, list)  # Check that the result is a list
    for game in games:
        assert 'game_date' in game  # Check that the 'game_date' column exists
        assert 'home_team' in game  # Check that the 'home_team' column exists
        assert 'away_team' in game  # Check that the 'away_team' column exists

def test_add_game(data_access):
    data_access.add_game('2023-10-01', 'Test Team', 'Another Team', 2, 1)
    games = data_access.get_all_games()
    assert 'Test Team' in [game['home_team'] for game in games] + [game['away_team'] for game in games]  # Check that the game was added