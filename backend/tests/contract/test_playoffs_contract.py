"""Contract tests for playoff bracket endpoints."""

import pytest

from api_client import AuthenticationError, AuthorizationError, MissingTableClient
from api_client.models import AdvanceWinnerRequest


@pytest.mark.contract
class TestPlayoffBracketContract:
    """Test playoff bracket endpoint contracts."""

    def test_get_playoff_bracket_requires_auth(self, api_client: MissingTableClient):
        """Test getting playoff bracket requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.get_playoff_bracket(league_id=1, season_id=1, age_group_id=1)

    def test_advance_playoff_winner_requires_auth(self, api_client: MissingTableClient):
        """Test advancing playoff winner requires authentication."""
        request = AdvanceWinnerRequest(slot_id=999)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.advance_playoff_winner(request)


@pytest.mark.contract
class TestAdminPlayoffContract:
    """Test admin playoff bracket endpoint contracts."""

    def test_generate_playoff_bracket_requires_auth(self, api_client: MissingTableClient):
        """Test generating playoff bracket requires authentication."""
        from api_client.models import GenerateBracketRequest

        request = GenerateBracketRequest(
            league_id=1,
            season_id=1,
            age_group_id=1,
            division_a_id=1,
            division_b_id=2,
            start_date="2026-03-01",
            tiers=[],
        )
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.generate_playoff_bracket(request)

    def test_advance_playoff_winner_admin_requires_auth(self, api_client: MissingTableClient):
        """Test admin advancing playoff winner requires authentication."""
        request = AdvanceWinnerRequest(slot_id=999)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.advance_playoff_winner_admin(request)

    def test_delete_playoff_bracket_requires_auth(self, api_client: MissingTableClient):
        """Test deleting playoff bracket requires authentication."""
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_playoff_bracket(league_id=1, season_id=1, age_group_id=1)
