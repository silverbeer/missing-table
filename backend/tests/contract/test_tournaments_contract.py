"""Contract tests for tournament endpoints."""

import pytest

from api_client import AuthenticationError, AuthorizationError, MissingTableClient
from api_client.models import TournamentCreate, TournamentMatchCreate


@pytest.mark.contract
class TestTournamentsReadContract:
    """Test read operations for tournament endpoints."""

    def test_get_active_tournaments_returns_list(self, api_client: MissingTableClient):
        """GET /api/tournaments is public and returns a list."""
        tournaments = api_client.get_active_tournaments()
        assert isinstance(tournaments, list)


@pytest.mark.contract
class TestTeamLookupContract:
    """Test admin team lookup endpoint."""

    def test_lookup_team_requires_auth(self, api_client: MissingTableClient):
        """Team lookup requires admin authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.lookup_team(name="Anything")


@pytest.mark.contract
class TestTournamentsWriteContract:
    """Test write operations for tournament endpoints."""

    def test_create_tournament_requires_auth(self, api_client: MissingTableClient):
        """Creating a tournament requires admin authentication."""
        payload = TournamentCreate(name="Test Tournament", start_date="2026-06-01")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_tournament(payload)

    def test_create_tournament_match_requires_auth(self, api_client: MissingTableClient):
        """Creating a tournament match requires admin authentication."""
        payload = TournamentMatchCreate(
            our_team_id=1,
            opponent_name="Opponent",
            match_date="2026-06-01",
            age_group_id=1,
            season_id=1,
        )
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_tournament_match(tournament_id=999999, match=payload)
