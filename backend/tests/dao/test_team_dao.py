"""
Comprehensive integration tests for TeamDAO.

Tests all team-related database operations including:
- Team CRUD operations
- Team queries and filters
- Team-age group mappings
- Team-match type participations
- Team-club associations
- Team statistics

These are integration tests that use a real test database (local Supabase).
No mocking - we test actual database interactions.
"""

import pytest

from dao.match_dao import SupabaseConnection
from dao.team_dao import TeamDAO

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def db_connection():
    """Create database connection for all tests in this module."""
    return SupabaseConnection()


@pytest.fixture(scope="module")
def team_dao(db_connection):
    """Create TeamDAO instance for testing."""
    return TeamDAO(db_connection)


@pytest.fixture(scope="module")
def test_data_ids(team_dao):
    """Get IDs of existing test data for use in tests.

    Rather than creating new test data, we use existing data from the restored backup.
    This is faster and tests against realistic data.
    """
    # Get first available IDs from each reference table
    age_groups = team_dao.client.table('age_groups').select('id').limit(3).execute()
    divisions = team_dao.client.table('divisions').select('id').limit(2).execute()
    match_types = team_dao.client.table('match_types').select('id').limit(2).execute()
    clubs = team_dao.client.table('clubs').select('id').limit(2).execute()

    return {
        'age_group_ids': [ag['id'] for ag in age_groups.data],
        'division_id': divisions.data[0]['id'] if divisions.data else None,
        'match_type_ids': [mt['id'] for mt in match_types.data],
        'club_id': clubs.data[0]['id'] if clubs.data else None,
    }


@pytest.fixture
def test_team_factory(team_dao, test_data_ids):
    """Factory fixture to create test teams and clean them up after test.

    Usage in tests:
        team_id = test_team_factory(name="Test Team", city="Boston")
    """
    created_team_ids = []

    _UNSET = object()  # Sentinel value to distinguish "not provided" from "explicitly None"

    def create_team(
        name="Test Team",
        city="Test City",
        age_group_ids=_UNSET,
        match_type_ids=_UNSET,
        division_id=_UNSET,
        club_id=None,
        academy_team=False
    ):
        """Create a test team and track for cleanup."""
        if age_group_ids is _UNSET:
            age_group_ids = [test_data_ids['age_group_ids'][0]]
        if match_type_ids is _UNSET:
            match_type_ids = [test_data_ids['match_type_ids'][0]]
        if division_id is _UNSET:
            division_id = test_data_ids['division_id']

        success = team_dao.add_team(
            name=name,
            city=city,
            age_group_ids=age_group_ids,
            match_type_ids=match_type_ids,
            division_id=division_id,
            club_id=club_id,
            academy_team=academy_team
        )

        if success:
            # Get the team ID
            team = team_dao.get_team_by_name(name)
            if team:
                created_team_ids.append(team['id'])
                return team['id']

        return None

    yield create_team

    # Cleanup: delete all created teams
    for team_id in created_team_ids:
        try:
            team_dao.delete_team(team_id)
        except Exception:
            pass  # Best effort cleanup


# ============================================================================
# Team Query Tests
# ============================================================================

@pytest.mark.integration
class TestTeamQueries:
    """Tests for team query methods."""

    def test_get_all_teams_returns_teams(self, team_dao):
        """Test get_all_teams() returns list of teams with age groups."""
        teams = team_dao.get_all_teams()

        assert isinstance(teams, list)
        assert len(teams) > 0

        # Check structure of first team
        first_team = teams[0]
        assert 'id' in first_team
        assert 'name' in first_team
        assert 'city' in first_team
        assert 'age_groups' in first_team
        assert isinstance(first_team['age_groups'], list)

    def test_get_all_teams_includes_divisions(self, team_dao):
        """Test get_all_teams() includes division information."""
        teams = team_dao.get_all_teams()

        # Find a team with divisions
        team_with_division = None
        for team in teams:
            if team.get('divisions_by_age_group'):
                team_with_division = team
                break

        if team_with_division:
            assert isinstance(team_with_division['divisions_by_age_group'], dict)

    def test_get_teams_by_match_type_and_age_group(self, team_dao, test_data_ids):
        """Test filtering teams by match type and age group."""
        match_type_id = test_data_ids['match_type_ids'][0]
        age_group_id = test_data_ids['age_group_ids'][0]

        teams = team_dao.get_teams_by_match_type_and_age_group(
            match_type_id=match_type_id,
            age_group_id=age_group_id
        )

        assert isinstance(teams, list)
        # Should return teams (if any exist with this match type)
        # Could be empty if no teams have this match type

    def test_get_teams_by_match_type_with_division_filter(self, team_dao, test_data_ids):
        """Test filtering teams by match type, age group, and division."""
        match_type_id = test_data_ids['match_type_ids'][0]
        age_group_id = test_data_ids['age_group_ids'][0]
        division_id = test_data_ids['division_id']

        teams = team_dao.get_teams_by_match_type_and_age_group(
            match_type_id=match_type_id,
            age_group_id=age_group_id,
            division_id=division_id
        )

        assert isinstance(teams, list)
        # Verify all returned teams are in the specified division
        for team in teams:
            if team.get('divisions_by_age_group'):
                # Check if this age group's division matches
                if age_group_id in team['divisions_by_age_group']:
                    assert team['divisions_by_age_group'][age_group_id]['id'] == division_id

    def test_get_team_by_name_case_insensitive(self, team_dao, test_team_factory):
        """Test get_team_by_name() is case-insensitive."""
        team_name = "Test Team Case Insensitive"
        team_id = test_team_factory(name=team_name)
        assert team_id is not None

        # Try lowercase
        result = team_dao.get_team_by_name(team_name.lower())
        assert result is not None
        assert result['id'] == team_id

        # Try uppercase
        result = team_dao.get_team_by_name(team_name.upper())
        assert result is not None
        assert result['id'] == team_id

    def test_get_team_by_name_not_found(self, team_dao):
        """Test get_team_by_name() returns None when team doesn't exist."""
        result = team_dao.get_team_by_name("NonExistent Team 99999")
        assert result is None

    def test_get_team_by_id_found(self, team_dao, test_team_factory):
        """Test get_team_by_id() returns team when found."""
        team_id = test_team_factory(name="Test Team By ID")
        assert team_id is not None

        result = team_dao.get_team_by_id(team_id)
        assert result is not None
        assert result['id'] == team_id
        assert 'name' in result
        assert 'city' in result

    def test_get_team_by_id_not_found(self, team_dao):
        """Test get_team_by_id() returns None when team doesn't exist."""
        result = team_dao.get_team_by_id(999999)
        assert result is None

    def test_get_team_with_details_includes_relationships(self, team_dao, test_team_factory, test_data_ids):
        """Test get_team_with_details() includes club, league, division."""
        team_id = test_team_factory(
            name="Test Team With Details",
            club_id=test_data_ids['club_id']
        )
        assert team_id is not None

        result = team_dao.get_team_with_details(team_id)
        assert result is not None
        assert result['id'] == team_id
        assert 'club' in result
        assert 'league' in result
        assert 'division' in result
        assert 'age_group' in result


# ============================================================================
# Team CRUD Tests
# ============================================================================

@pytest.mark.integration
class TestTeamCRUD:
    """Tests for team create, read, update, delete operations."""

    def test_add_team_success(self, team_dao, test_data_ids):
        """Test creating a team successfully."""
        success = team_dao.add_team(
            name="Test Team CRUD Create",
            city="Boston",
            age_group_ids=[test_data_ids['age_group_ids'][0]],
            match_type_ids=[test_data_ids['match_type_ids'][0]],
            division_id=test_data_ids['division_id'],
            club_id=test_data_ids['club_id']
        )

        assert success is True

        # Verify team was created
        team = team_dao.get_team_by_name("Test Team CRUD Create")
        assert team is not None

        # Cleanup
        team_dao.delete_team(team['id'])

    def test_add_team_with_multiple_age_groups(self, team_dao, test_data_ids):
        """Test creating a team with multiple age groups."""
        age_group_ids = test_data_ids['age_group_ids'][:2]  # Use first 2

        success = team_dao.add_team(
            name="Test Multi Age Group Team",
            city="Boston",
            age_group_ids=age_group_ids,
            match_type_ids=[test_data_ids['match_type_ids'][0]],
            division_id=test_data_ids['division_id']
        )

        assert success is True

        # Verify team has both age groups
        team = team_dao.get_team_by_name("Test Multi Age Group Team")
        assert team is not None

        teams = team_dao.get_all_teams()
        created_team = next((t for t in teams if t['id'] == team['id']), None)
        assert created_team is not None
        assert len(created_team['age_groups']) == 2

        # Cleanup
        team_dao.delete_team(team['id'])

    def test_add_guest_team_without_division(self, team_dao, test_data_ids):
        """Test creating a guest/tournament team without division."""
        success = team_dao.add_team(
            name="Test Guest Team",
            city="Boston",
            age_group_ids=[test_data_ids['age_group_ids'][0]],
            match_type_ids=[test_data_ids['match_type_ids'][0]],
            division_id=None,  # No division for guest teams
            club_id=None
        )

        assert success is True

        # Verify team was created
        team = team_dao.get_team_by_name("Test Guest Team")
        assert team is not None

        # Cleanup
        team_dao.delete_team(team['id'])

    def test_add_team_missing_required_fields(self, team_dao):
        """Test creating team with missing required fields fails."""
        # Missing age_group_ids should raise ValueError
        with pytest.raises(ValueError, match="at least one age group"):
            team_dao.add_team(
                name="Test Invalid Team",
                city="Boston",
                age_group_ids=[],  # Empty age groups
                match_type_ids=None,
                division_id=None
            )

    def test_add_team_invalid_division(self, team_dao, test_data_ids):
        """Test creating team with non-existent division fails."""
        with pytest.raises(ValueError, match="Division .* not found"):
            team_dao.add_team(
                name="Test Invalid Division Team",
                city="Boston",
                age_group_ids=[test_data_ids['age_group_ids'][0]],
                match_type_ids=None,
                division_id=999999  # Non-existent division
            )

    @pytest.mark.skip(reason="Schema doesn't enforce team name uniqueness - technical debt")
    def test_add_duplicate_team_fails(self, team_dao, test_team_factory, test_data_ids):
        """Test creating duplicate team raises exception.

        NOTE: Currently skipped because the teams table doesn't have a unique constraint
        on (name, division_id). This is technical debt that should be addressed by adding
        the constraint to the schema.
        """
        team_name = "Test Duplicate Team"
        team_id = test_team_factory(name=team_name)
        assert team_id is not None

        # Try to create duplicate - should raise exception
        with pytest.raises(Exception):  # Will be caught and re-raised by add_team
            team_dao.add_team(
                name=team_name,  # Same name
                city="Boston",
                age_group_ids=[test_data_ids['age_group_ids'][0]],
                match_type_ids=[test_data_ids['match_type_ids'][0]],
                division_id=test_data_ids['division_id']
            )

    def test_update_team_basic_fields(self, team_dao, test_team_factory):
        """Test updating team name, city, and academy_team flag."""
        team_id = test_team_factory(name="Test Update Team Original")
        assert team_id is not None

        # Update team
        result = team_dao.update_team(
            team_id=team_id,
            name="Test Update Team Modified",
            city="New City",
            academy_team=True,
            club_id=None
        )

        assert result is not None
        assert result['name'] == "Test Update Team Modified"
        assert result['city'] == "New City"
        assert result['academy_team'] is True

    def test_update_team_not_found(self, team_dao):
        """Test updating non-existent team returns None."""
        result = team_dao.update_team(
            team_id=999999,
            name="Test",
            city="Test"
        )

        assert result is None

    def test_delete_team_success(self, team_dao, test_team_factory):
        """Test deleting a team and its related data."""
        team_id = test_team_factory(name="Test Delete Team")
        assert team_id is not None

        # Verify team exists
        team = team_dao.get_team_by_id(team_id)
        assert team is not None

        # Delete team
        result = team_dao.delete_team(team_id)
        assert result is True

        # Verify team no longer exists
        team = team_dao.get_team_by_id(team_id)
        assert team is None

    def test_delete_team_cascades_to_mappings(self, team_dao, test_team_factory):
        """Test deleting team removes team_mappings."""
        team_id = test_team_factory(name="Test Delete Cascade Team")
        assert team_id is not None

        # Verify team has mappings
        mappings = team_dao.client.table('team_mappings').select('*').eq('team_id', team_id).execute()
        assert len(mappings.data) > 0

        # Delete team
        team_dao.delete_team(team_id)

        # Verify mappings are gone
        mappings = team_dao.client.table('team_mappings').select('*').eq('team_id', team_id).execute()
        assert len(mappings.data) == 0


# ============================================================================
# Team Mapping Tests
# ============================================================================

@pytest.mark.integration
class TestTeamMappings:
    """Tests for team-division-age group mappings."""

    def test_create_team_mapping_updates_league(self, team_dao, test_team_factory, test_data_ids):
        """Test creating mapping updates team's league_id from division."""
        team_id = test_team_factory(
            name="Test Mapping League Update",
            division_id=None  # Create without division
        )
        assert team_id is not None

        age_group_id = test_data_ids['age_group_ids'][1]  # Use different age group
        division_id = test_data_ids['division_id']

        # Create mapping
        result = team_dao.create_team_mapping(team_id, age_group_id, division_id)
        assert result is not None

        # Verify team's league_id was updated
        team = team_dao.client.table('teams').select('league_id').eq('id', team_id).execute()
        assert team.data[0]['league_id'] is not None

    def test_create_mapping_auto_enables_league_match_type(self, team_dao, test_team_factory, test_data_ids):
        """Test creating mapping auto-creates League match type participation."""
        team_id = test_team_factory(
            name="Test Auto League Participation",
            match_type_ids=[],  # No match types initially
            division_id=None
        )
        assert team_id is not None

        age_group_id = test_data_ids['age_group_ids'][0]
        division_id = test_data_ids['division_id']

        # Create mapping
        team_dao.create_team_mapping(team_id, age_group_id, division_id)

        # Verify League match type (id=1) was auto-created
        LEAGUE_MATCH_TYPE_ID = 1
        participation = team_dao.client.table('team_match_types').select('*')\
            .eq('team_id', team_id)\
            .eq('match_type_id', LEAGUE_MATCH_TYPE_ID)\
            .eq('age_group_id', age_group_id)\
            .execute()

        assert len(participation.data) > 0
        assert participation.data[0]['is_active'] is True

    def test_update_team_division(self, team_dao, test_team_factory, test_data_ids):
        """Test updating team's division for an age group."""
        # Get two different divisions
        divisions = team_dao.client.table('divisions').select('id').limit(2).execute()
        if len(divisions.data) < 2:
            pytest.skip("Need at least 2 divisions for this test")

        division_id_1 = divisions.data[0]['id']
        division_id_2 = divisions.data[1]['id']

        team_id = test_team_factory(name="Test Update Division", division_id=division_id_1)
        assert team_id is not None

        age_group_id = test_data_ids['age_group_ids'][0]

        # Update to different division
        result = team_dao.update_team_division(team_id, age_group_id, division_id_2)
        assert result is True

        # Verify division was updated
        mapping = team_dao.client.table('team_mappings').select('division_id')\
            .eq('team_id', team_id)\
            .eq('age_group_id', age_group_id)\
            .execute()

        assert mapping.data[0]['division_id'] == division_id_2

    def test_delete_team_mapping(self, team_dao, test_team_factory, test_data_ids):
        """Test deleting a team-age group-division mapping."""
        team_id = test_team_factory(name="Test Delete Mapping")
        assert team_id is not None

        age_group_id = test_data_ids['age_group_ids'][0]
        division_id = test_data_ids['division_id']

        # Verify mapping exists
        mapping = team_dao.client.table('team_mappings').select('*')\
            .eq('team_id', team_id)\
            .eq('age_group_id', age_group_id)\
            .eq('division_id', division_id)\
            .execute()

        if len(mapping.data) == 0:
            pytest.skip("No mapping to delete")

        # Delete mapping
        result = team_dao.delete_team_mapping(team_id, age_group_id, division_id)
        assert result is True

        # Verify mapping is gone
        mapping = team_dao.client.table('team_mappings').select('*')\
            .eq('team_id', team_id)\
            .eq('age_group_id', age_group_id)\
            .eq('division_id', division_id)\
            .execute()

        assert len(mapping.data) == 0


# ============================================================================
# Match Type Participation Tests
# ============================================================================

@pytest.mark.integration
class TestMatchTypeParticipation:
    """Tests for team match type participation."""

    def test_add_match_type_participation(self, team_dao, test_team_factory, test_data_ids):
        """Test adding team participation in a match type."""
        team_id = test_team_factory(
            name="Test Add Match Type",
            match_type_ids=[]  # No match types initially
        )
        assert team_id is not None

        match_type_id = test_data_ids['match_type_ids'][1]  # Different match type
        age_group_id = test_data_ids['age_group_ids'][0]

        # Add participation
        result = team_dao.add_team_match_type_participation(
            team_id, match_type_id, age_group_id
        )
        assert result is True

        # Verify participation was added
        participation = team_dao.client.table('team_match_types').select('*')\
            .eq('team_id', team_id)\
            .eq('match_type_id', match_type_id)\
            .eq('age_group_id', age_group_id)\
            .execute()

        assert len(participation.data) > 0
        assert participation.data[0]['is_active'] is True

    def test_remove_match_type_participation(self, team_dao, test_team_factory, test_data_ids):
        """Test removing team participation (sets is_active to False)."""
        team_id = test_team_factory(name="Test Remove Match Type")
        assert team_id is not None

        match_type_id = test_data_ids['match_type_ids'][0]
        age_group_id = test_data_ids['age_group_ids'][0]

        # Ensure participation exists
        team_dao.add_team_match_type_participation(team_id, match_type_id, age_group_id)

        # Remove participation
        result = team_dao.remove_team_match_type_participation(
            team_id, match_type_id, age_group_id
        )
        assert result is True

        # Verify is_active is now False
        participation = team_dao.client.table('team_match_types').select('is_active')\
            .eq('team_id', team_id)\
            .eq('match_type_id', match_type_id)\
            .eq('age_group_id', age_group_id)\
            .execute()

        assert len(participation.data) > 0
        assert participation.data[0]['is_active'] is False


# ============================================================================
# Club Association Tests
# ============================================================================

@pytest.mark.integration
class TestClubAssociations:
    """Tests for team-club relationships."""

    def test_get_club_teams(self, team_dao, test_data_ids):
        """Test getting all teams for a club."""
        club_id = test_data_ids['club_id']

        teams = team_dao.get_club_teams(club_id)

        assert isinstance(teams, list)
        # All teams should belong to this club
        for team in teams:
            assert team['club_id'] == club_id

    def test_get_club_teams_includes_counts(self, team_dao, test_data_ids):
        """Test club teams include match_count and player_count."""
        club_id = test_data_ids['club_id']

        teams = team_dao.get_club_teams(club_id)

        if teams:
            first_team = teams[0]
            assert 'match_count' in first_team
            assert 'player_count' in first_team
            assert isinstance(first_team['match_count'], int)
            assert isinstance(first_team['player_count'], int)

    def test_get_club_for_team(self, team_dao, test_team_factory, test_data_ids):
        """Test getting club details for a team."""
        club_id = test_data_ids['club_id']
        team_id = test_team_factory(
            name="Test Get Club For Team",
            club_id=club_id
        )
        assert team_id is not None

        club = team_dao.get_club_for_team(team_id)

        assert club is not None
        assert club['id'] == club_id
        assert 'name' in club

    def test_get_club_for_team_without_club(self, team_dao, test_team_factory):
        """Test returns None for team without club."""
        team_id = test_team_factory(
            name="Test No Club Team",
            club_id=None
        )
        assert team_id is not None

        club = team_dao.get_club_for_team(team_id)
        assert club is None

    def test_update_team_club(self, team_dao, test_team_factory, test_data_ids):
        """Test changing team's club association."""
        team_id = test_team_factory(
            name="Test Update Club",
            club_id=None
        )
        assert team_id is not None

        club_id = test_data_ids['club_id']

        # Update club
        result = team_dao.update_team_club(team_id, club_id)

        assert result is not None
        assert result['club_id'] == club_id


# ============================================================================
# Team Statistics Tests
# ============================================================================

@pytest.mark.integration
class TestTeamStatistics:
    """Tests for team statistics methods."""

    @pytest.mark.skip(reason="Database function get_team_game_counts doesn't exist in schema")
    def test_get_team_game_counts_returns_dict(self, team_dao):
        """Test get_team_game_counts() returns dictionary.

        NOTE: Skipped because the PostgreSQL function get_team_game_counts() doesn't exist
        in the local schema. This needs to be added via a migration.
        """
        counts = team_dao.get_team_game_counts()

        assert isinstance(counts, dict)
        # Dictionary maps team_id (int) to game_count (int)
        for team_id, count in counts.items():
            assert isinstance(team_id, int)
            assert isinstance(count, int)
            assert count >= 0

    @pytest.mark.skip(reason="Database function get_team_game_counts doesn't exist in schema")
    def test_get_team_game_counts_includes_existing_teams(self, team_dao):
        """Test game counts include teams with matches.

        NOTE: Skipped because the PostgreSQL function get_team_game_counts() doesn't exist
        in the local schema. This needs to be added via a migration.
        """
        # Get teams that should have matches
        teams = team_dao.get_all_teams()
        counts = team_dao.get_team_game_counts()

        # At least some teams should have match counts
        teams_with_matches = [tid for tid, count in counts.items() if count > 0]
        assert len(teams_with_matches) > 0


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

@pytest.mark.integration
class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_get_all_teams_with_no_age_groups(self, team_dao):
        """Test handling teams with no age groups (shouldn't happen but test anyway)."""
        teams = team_dao.get_all_teams()
        # Should not crash, returns empty age_groups list
        assert isinstance(teams, list)

    def test_operations_with_invalid_team_id(self, team_dao):
        """Test operations with non-existent team ID."""
        invalid_id = 999999

        # All should handle gracefully
        assert team_dao.get_team_by_id(invalid_id) is None
        assert team_dao.update_team(invalid_id, "Test", "Test") is None

        # Delete returns False for non-existent
        # (Actually deletes related data first, but team delete returns False)
        result = team_dao.delete_team(invalid_id)
        assert result is False

    def test_get_club_teams_empty_club(self, team_dao):
        """Test getting teams for club with no teams."""
        # Find a club with no teams (or use very high ID)
        result = team_dao.get_club_teams(999999)
        assert isinstance(result, list)
        assert len(result) == 0
