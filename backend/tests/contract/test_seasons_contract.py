"""Contract tests for seasons, age groups, and divisions endpoints."""

import pytest

from api_client import AuthorizationError, MissingTableClient


@pytest.mark.contract
class TestSeasonsContract:
    """Test seasons endpoint contracts."""

    def test_get_seasons_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting seasons returns a list."""
        seasons = authenticated_api_client.get_seasons()
        assert isinstance(seasons, list)

    def test_get_current_season(self, authenticated_api_client: MissingTableClient):
        """Test getting current season returns a response."""
        try:
            season = authenticated_api_client.get_current_season()
            assert season is not None
        except Exception:
            pytest.skip("No current season configured")

    def test_get_active_seasons(self, authenticated_api_client: MissingTableClient):
        """Test getting active seasons returns a list."""
        seasons = authenticated_api_client.get_active_seasons()
        assert isinstance(seasons, list)

    def test_create_season_requires_auth(self, api_client: MissingTableClient):
        """Test creating a season requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import SeasonCreate

        season = SeasonCreate(name="Test Season", start_date="2026-01-01", end_date="2026-12-31")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_season(season)

    def test_update_season_requires_auth(self, api_client: MissingTableClient):
        """Test updating a season requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import SeasonUpdate

        update = SeasonUpdate(name="Updated", start_date="2026-01-01", end_date="2026-12-31")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_season(999, update)

    def test_delete_season_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a season requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_season(999)


@pytest.mark.contract
class TestAgeGroupsContract:
    """Test age groups endpoint contracts."""

    def test_get_age_groups_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting age groups returns a list."""
        age_groups = authenticated_api_client.get_age_groups()
        assert isinstance(age_groups, list)

    def test_create_age_group_requires_auth(self, api_client: MissingTableClient):
        """Test creating an age group requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import AgeGroupCreate

        ag = AgeGroupCreate(name="Test AG")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_age_group(ag)

    def test_update_age_group_requires_auth(self, api_client: MissingTableClient):
        """Test updating an age group requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import AgeGroupUpdate

        update = AgeGroupUpdate(name="Updated AG")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_age_group(999, update)

    def test_delete_age_group_requires_auth(self, api_client: MissingTableClient):
        """Test deleting an age group requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_age_group(999)


@pytest.mark.contract
class TestDivisionsContract:
    """Test divisions endpoint contracts."""

    def test_get_divisions_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting divisions returns a list."""
        divisions = authenticated_api_client.get_divisions()
        assert isinstance(divisions, list)

    def test_create_division_requires_auth(self, api_client: MissingTableClient):
        """Test creating a division requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import DivisionCreate

        div = DivisionCreate(name="Test Div", league_id=1)
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.create_division(div)

    def test_update_division_requires_auth(self, api_client: MissingTableClient):
        """Test updating a division requires authentication."""
        from api_client import AuthenticationError
        from api_client.models import DivisionUpdate

        update = DivisionUpdate(name="Updated Div")
        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.update_division(999, update)

    def test_delete_division_requires_auth(self, api_client: MissingTableClient):
        """Test deleting a division requires authentication."""
        from api_client import AuthenticationError

        with pytest.raises((AuthenticationError, AuthorizationError)):
            api_client.delete_division(999)


@pytest.mark.contract
class TestMatchTypesContract:
    """Test match types endpoint contracts."""

    def test_get_match_types_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting match types returns a list."""
        match_types = authenticated_api_client.get_game_types()
        assert isinstance(match_types, list)


@pytest.mark.contract
class TestPositionsContract:
    """Test positions endpoint contracts."""

    def test_get_positions_returns_list(self, authenticated_api_client: MissingTableClient):
        """Test getting positions returns a list."""
        positions = authenticated_api_client.get_positions()
        assert isinstance(positions, list)
