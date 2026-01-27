"""Contract tests for standings and leaderboard endpoints."""

import pytest

from api_client import MissingTableClient


@pytest.mark.contract
class TestStandingsContract:
    """Test standings endpoint contracts."""

    def test_get_table_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting league table returns a list."""
        table = authenticated_api_client.get_table()
        assert isinstance(table, list)

    def test_get_table_with_filters(self, authenticated_api_client: MissingTableClient):
        """Test getting league table with filters."""
        table = authenticated_api_client.get_table(season_id=1)
        assert isinstance(table, list)


@pytest.mark.contract
class TestLeaderboardsContract:
    """Test leaderboard endpoint contracts."""

    def test_get_goals_leaderboard(self, authenticated_api_client: MissingTableClient):
        """Test getting goals leaderboard returns a list."""
        leaderboard = authenticated_api_client.get_goals_leaderboard(season_id=1)
        assert isinstance(leaderboard, list)
