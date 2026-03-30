"""
Tests for the MatchDAO layer.
"""

import pytest

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
    assert hasattr(enhanced_dao, 'get_all_matches')
    assert hasattr(enhanced_dao, 'get_matches_by_team')
    assert hasattr(enhanced_dao, 'get_league_table')


@pytest.mark.integration
def test_get_all_matches(enhanced_dao):
    """Test getting all matches returns a list."""
    matches = enhanced_dao.get_all_matches()
    assert isinstance(matches, list)

    if matches:
        match = matches[0]
        expected_fields = ['id', 'match_date', 'home_team_id', 'away_team_id']
        for field in expected_fields:
            assert field in match, f"Match missing field: {field}"


@pytest.mark.integration
def test_get_all_matches_with_filters(enhanced_dao):
    """Test getting matches with season_id filter."""
    matches = enhanced_dao.get_all_matches(season_id=1)
    assert isinstance(matches, list)

    if matches:
        for match in matches:
            assert match.get('season_id') == 1


@pytest.mark.integration
def test_get_matches_by_team_nonexistent(enhanced_dao):
    """Test getting matches for a non-existent team returns empty list."""
    matches = enhanced_dao.get_matches_by_team(team_id=999999)
    assert isinstance(matches, list)
    assert len(matches) == 0


@pytest.mark.integration
def test_get_league_table(enhanced_dao):
    """Test getting league table returns a list."""
    table = enhanced_dao.get_league_table()
    assert isinstance(table, list)

    if table:
        entry = table[0]
        expected_fields = ['team', 'played', 'wins', 'draws', 'losses', 'points']
        for field in expected_fields:
            assert field in entry, f"League table entry missing field: {field}"


@pytest.mark.integration
def test_get_match_by_id_nonexistent(enhanced_dao):
    """Test getting a non-existent match by ID returns None."""
    match = enhanced_dao.get_match_by_id(match_id=999999)
    assert match is None


@pytest.mark.integration
def test_dao_error_handling(enhanced_dao):
    """Test DAO handles invalid inputs gracefully."""
    matches = enhanced_dao.get_matches_by_team(team_id=999999)
    assert isinstance(matches, list)
    assert len(matches) == 0
