"""Contract tests for teams endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient, NotFoundError


@pytest.mark.contract
class TestTeamsReadContract:
    """Test read operations for teams endpoints."""

    def test_get_teams_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting all teams returns a list."""
        teams = authenticated_api_client.get_teams()
        assert isinstance(teams, list)

    def test_get_team_not_found(self, authenticated_api_client: MissingTableClient):
        """Test getting non-existent team returns an error."""
        from api_client import APIError

        with pytest.raises((NotFoundError, APIError)):
            authenticated_api_client.get_team(999999)

    def test_get_team_players(self, authenticated_api_client: MissingTableClient):
        """Test getting team players returns a response."""
        teams = authenticated_api_client.get_teams()
        if not teams:
            pytest.skip("No teams available")
        try:
            result = authenticated_api_client.get_team_players(teams[0]["id"])
            assert isinstance(result, list | dict)
        except AuthorizationError:
            pytest.skip("User does not have permission to view this team's players")

    def test_get_team_stats(self, authenticated_api_client: MissingTableClient):
        """Test getting team stats returns a response."""
        teams = authenticated_api_client.get_teams()
        if not teams:
            pytest.skip("No teams available")
        result = authenticated_api_client.get_team_stats(teams[0]["id"], season_id=1)
        assert result is not None


@pytest.mark.contract
class TestTeamsWriteContract:
    """Test write operations for teams endpoints."""

    def test_create_team_requires_auth(self, api_client: MissingTableClient):
        """Test creating a team requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import Team

        team = Team(name="Contract Test Team", city="Test City", age_group_ids=[1], division_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_team(team)

    def test_update_team_requires_auth(self, api_client: MissingTableClient):
        """Test updating a team requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import Team

        team = Team(name="Updated", city="City", age_group_ids=[1], division_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_team(999, team)

    def test_delete_team_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a team requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_team(999)


@pytest.mark.contract
class TestTeamMatchTypesContract:
    """Test team match type endpoints."""

    def test_add_team_match_type_requires_auth(self, api_client: MissingTableClient):
        """Test adding match type requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.add_team_match_type(1, 1, 1)

    def test_delete_team_match_type_requires_auth(self, api_client: MissingTableClient):
        """Test removing match type requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_team_match_type(1, 1, 1)


@pytest.mark.contract
class TestTeamRosterContract:
    """Test team roster endpoints."""

    def test_get_team_roster(self, authenticated_api_client: MissingTableClient):
        """Test getting team roster returns a response."""
        teams = authenticated_api_client.get_teams()
        if not teams:
            pytest.skip("No teams available")
        result = authenticated_api_client.get_team_roster(teams[0]["id"], season_id=1)
        assert result is not None

    def test_create_roster_entry_requires_auth(self, api_client: MissingTableClient):
        """Test creating a roster entry requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import RosterPlayerCreate

        entry = RosterPlayerCreate(jersey_number=99, season_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_roster_entry(1, entry)

    def test_bulk_create_roster_requires_auth(self, api_client: MissingTableClient):
        """Test bulk roster creation requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import BulkRosterCreate, BulkRosterPlayer

        bulk = BulkRosterCreate(season_id=1, players=[BulkRosterPlayer(jersey_number=1)])
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.bulk_create_roster(1, bulk)

    def test_update_roster_entry_requires_auth(self, api_client: MissingTableClient):
        """Test updating roster entry requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import RosterPlayerUpdate

        update = RosterPlayerUpdate(first_name="Test")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_roster_entry(1, 1, update)

    def test_update_jersey_number_requires_auth(self, api_client: MissingTableClient):
        """Test updating jersey number requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import JerseyNumberUpdate

        update = JerseyNumberUpdate(new_number=42)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_jersey_number(1, 1, update)

    def test_bulk_renumber_requires_auth(self, api_client: MissingTableClient):
        """Test bulk renumber requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import BulkRenumberRequest, RenumberEntry

        req = BulkRenumberRequest(changes=[RenumberEntry(player_id=1, new_number=10)])
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.bulk_renumber_roster(1, req)

    def test_delete_roster_entry_requires_auth(self, api_client: MissingTableClient):
        """Test deleting roster entry requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_roster_entry(1, 1)
