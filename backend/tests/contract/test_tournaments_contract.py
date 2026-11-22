"""Contract tests for tournament endpoints."""

import pytest

from api_client import AuthenticationError, AuthorizationError, MissingTableClient, NotFoundError
from api_client.models import TournamentCreate, TournamentMatchCreate


@pytest.mark.contract
class TestTournamentsReadContract:
    """Test read operations for tournament endpoints."""

    def test_get_active_tournaments_returns_list(self, api_client: MissingTableClient):
        """GET /api/tournaments is public and returns a list."""
        tournaments = api_client.get_active_tournaments()
        assert isinstance(tournaments, list)


@pytest.mark.contract
class TestTournamentMatchesPagingContract:
    """GET /api/tournaments/{id}/matches and /filters (SB-1749).

    Run against whatever tournament the server has; with none, only the 404
    contract can be checked.
    """

    @staticmethod
    def _any_tournament_id(api_client: MissingTableClient) -> int:
        tournaments = api_client.get_active_tournaments()
        if not tournaments:
            pytest.skip("No active tournament on this server")
        return tournaments[0]["id"]

    def test_matches_page_shape(self, api_client: MissingTableClient):
        """A page is {matches, total, limit, offset} and never longer than its limit."""
        tournament_id = self._any_tournament_id(api_client)
        page = api_client.get_tournament_matches(tournament_id, limit=5)
        assert set(page) == {"matches", "total", "limit", "offset"}
        assert page["limit"] == 5
        assert page["offset"] == 0
        assert len(page["matches"]) <= 5
        assert page["total"] >= len(page["matches"])

    def test_matches_limit_is_capped(self, api_client: MissingTableClient):
        """An oversized limit is clamped, not rejected."""
        tournament_id = self._any_tournament_id(api_client)
        assert api_client.get_tournament_matches(tournament_id, limit=100000)["limit"] == 500

    def test_unknown_round_matches_nothing(self, api_client: MissingTableClient):
        """A filter that cannot match is an empty 200, never the unfiltered list."""
        tournament_id = self._any_tournament_id(api_client)
        page = api_client.get_tournament_matches(tournament_id, round="not_a_round")
        assert page["matches"] == []
        assert page["total"] == 0

    def test_matches_unknown_tournament_is_404(self, api_client: MissingTableClient):
        with pytest.raises(NotFoundError):
            api_client.get_tournament_matches(999999999)

    def test_filters_shape(self, api_client: MissingTableClient):
        """Filters list age groups; groups is a list, or null when unknown."""
        tournament_id = self._any_tournament_id(api_client)
        filters = api_client.get_tournament_filters(tournament_id)
        assert set(filters) == {"facets_available", "age_groups", "groups"}
        assert isinstance(filters["age_groups"], list)
        for age_group in filters["age_groups"]:
            assert set(age_group) == {"id", "name", "matches", "matches_on_date"}
        if filters["facets_available"]:
            assert isinstance(filters["groups"], list)
        else:
            # Unknown is null, not an empty list and not zero.
            assert filters["groups"] is None
            assert all(ag["matches"] is None for ag in filters["age_groups"])

    def test_filters_unknown_tournament_is_404(self, api_client: MissingTableClient):
        with pytest.raises(NotFoundError):
            api_client.get_tournament_filters(999999999)


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
