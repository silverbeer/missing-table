"""
Authorization Matrix Testing - Comprehensive permission coverage in a single test.

This module demonstrates innovative parameterized testing by covering ALL
role/permission combinations for team management and match editing in one
elegant matrix test. Business rules are self-documenting through the test data.

Business Rules Documented:
- admin: Can manage any team, can edit any match
- team-manager: Can manage own team only, can edit matches involving own team
- club_manager: Can manage teams in their club, can edit matches with club teams
- team-fan: Cannot manage any team, cannot edit any match
- service_account: With manage_matches permission can edit any match

Usage:
    pytest tests/unit/test_authorization_matrix.py -v
    pytest tests/unit/test_authorization_matrix.py -k "can_manage" -v
"""

import pytest
import allure
from unittest.mock import Mock, patch
from dataclasses import dataclass
from typing import Optional, List

import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from auth import AuthManager


@dataclass
class TeamPermissionScenario:
    """Represents a single team management authorization test scenario."""
    id: str
    role: str
    user_team_id: Optional[int]
    user_club_id: Optional[int]
    target_team_id: int
    target_team_club_id: Optional[int]
    expected: bool
    description: str


@dataclass
class MatchPermissionScenario:
    """Represents a match editing permission test scenario."""
    id: str
    role: str
    user_team_id: Optional[int]
    user_club_id: Optional[int]
    permissions: List[str]
    home_team_id: int
    away_team_id: int
    home_team_club_id: Optional[int]
    away_team_club_id: Optional[int]
    expected: bool
    description: str


# ============================================================================
# PERMISSION MATRIX: can_manage_team()
# ============================================================================
# This matrix documents ALL business rules for team management authorization

TEAM_MANAGEMENT_SCENARIOS = [
    # --- ADMIN SCENARIOS (should always succeed) ---
    TeamPermissionScenario(
        id="admin_any_team",
        role="admin",
        user_team_id=1,
        user_club_id=None,
        target_team_id=999,
        target_team_club_id=None,
        expected=True,
        description="Admin can manage any team regardless of affiliation"
    ),
    TeamPermissionScenario(
        id="admin_no_team_assignment",
        role="admin",
        user_team_id=None,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=10,
        expected=True,
        description="Admin without team assignment can still manage any team"
    ),

    # --- TEAM MANAGER SCENARIOS ---
    TeamPermissionScenario(
        id="team_manager_own_team",
        role="team-manager",
        user_team_id=5,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=None,
        expected=True,
        description="Team manager can manage their own team"
    ),
    TeamPermissionScenario(
        id="team_manager_other_team",
        role="team-manager",
        user_team_id=5,
        user_club_id=None,
        target_team_id=10,
        target_team_club_id=None,
        expected=False,
        description="Team manager cannot manage a different team"
    ),
    TeamPermissionScenario(
        id="team_manager_no_assignment",
        role="team-manager",
        user_team_id=None,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=None,
        expected=False,
        description="Team manager without team assignment cannot manage any team"
    ),

    # --- CLUB MANAGER SCENARIOS ---
    TeamPermissionScenario(
        id="club_manager_team_in_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        target_team_id=5,
        target_team_club_id=100,
        expected=True,
        description="Club manager can manage team in their club"
    ),
    TeamPermissionScenario(
        id="club_manager_team_different_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        target_team_id=5,
        target_team_club_id=200,
        expected=False,
        description="Club manager cannot manage team in different club"
    ),
    TeamPermissionScenario(
        id="club_manager_team_no_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        target_team_id=5,
        target_team_club_id=None,
        expected=False,
        description="Club manager cannot manage team with no club affiliation"
    ),
    TeamPermissionScenario(
        id="club_manager_no_club_assignment",
        role="club_manager",
        user_team_id=None,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=100,
        expected=False,
        description="Club manager without club assignment cannot manage any team"
    ),

    # --- TEAM FAN SCENARIOS (should always fail) ---
    TeamPermissionScenario(
        id="team_fan_own_team",
        role="team-fan",
        user_team_id=5,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=None,
        expected=False,
        description="Team fan cannot manage even their own team"
    ),
    TeamPermissionScenario(
        id="team_fan_any_team",
        role="team-fan",
        user_team_id=5,
        user_club_id=None,
        target_team_id=10,
        target_team_club_id=None,
        expected=False,
        description="Team fan cannot manage any team"
    ),

    # --- REGULAR USER SCENARIOS ---
    TeamPermissionScenario(
        id="user_any_team",
        role="user",
        user_team_id=None,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=None,
        expected=False,
        description="Regular user cannot manage any team"
    ),

    # --- SERVICE ACCOUNT SCENARIOS ---
    TeamPermissionScenario(
        id="service_account_any_team",
        role="service_account",
        user_team_id=None,
        user_club_id=None,
        target_team_id=5,
        target_team_club_id=None,
        expected=False,
        description="Service account cannot manage teams (only matches)"
    ),
]


# ============================================================================
# PERMISSION MATRIX: can_edit_match()
# ============================================================================
# This matrix documents ALL business rules for match editing authorization

MATCH_EDITING_SCENARIOS = [
    # --- ADMIN SCENARIOS ---
    MatchPermissionScenario(
        id="admin_any_match",
        role="admin",
        user_team_id=None,
        user_club_id=None,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=True,
        description="Admin can edit any match"
    ),

    # --- SERVICE ACCOUNT SCENARIOS ---
    MatchPermissionScenario(
        id="service_with_manage_matches",
        role="service_account",
        user_team_id=None,
        user_club_id=None,
        permissions=["manage_matches"],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=True,
        description="Service account with manage_matches can edit any match"
    ),
    MatchPermissionScenario(
        id="service_with_read_only",
        role="service_account",
        user_team_id=None,
        user_club_id=None,
        permissions=["read_only"],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Service account without manage_matches cannot edit"
    ),
    MatchPermissionScenario(
        id="service_empty_permissions",
        role="service_account",
        user_team_id=None,
        user_club_id=None,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Service account with no permissions cannot edit"
    ),
    MatchPermissionScenario(
        id="service_with_multiple_permissions",
        role="service_account",
        user_team_id=None,
        user_club_id=None,
        permissions=["read_data", "manage_matches", "sync_teams"],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=True,
        description="Service account with manage_matches among multiple permissions can edit"
    ),

    # --- TEAM MANAGER SCENARIOS ---
    MatchPermissionScenario(
        id="team_manager_home_team",
        role="team-manager",
        user_team_id=5,
        user_club_id=None,
        permissions=[],
        home_team_id=5,
        away_team_id=10,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=True,
        description="Team manager can edit match when their team is home"
    ),
    MatchPermissionScenario(
        id="team_manager_away_team",
        role="team-manager",
        user_team_id=5,
        user_club_id=None,
        permissions=[],
        home_team_id=10,
        away_team_id=5,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=True,
        description="Team manager can edit match when their team is away"
    ),
    MatchPermissionScenario(
        id="team_manager_neither_team",
        role="team-manager",
        user_team_id=5,
        user_club_id=None,
        permissions=[],
        home_team_id=10,
        away_team_id=20,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Team manager cannot edit match when neither team is theirs"
    ),
    MatchPermissionScenario(
        id="team_manager_no_team_assigned",
        role="team-manager",
        user_team_id=None,
        user_club_id=None,
        permissions=[],
        home_team_id=5,
        away_team_id=10,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Team manager without team cannot edit any match"
    ),

    # --- CLUB MANAGER SCENARIOS ---
    MatchPermissionScenario(
        id="club_manager_home_in_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=100,
        away_team_club_id=200,
        expected=True,
        description="Club manager can edit when home team is in their club"
    ),
    MatchPermissionScenario(
        id="club_manager_away_in_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=200,
        away_team_club_id=100,
        expected=True,
        description="Club manager can edit when away team is in their club"
    ),
    MatchPermissionScenario(
        id="club_manager_both_in_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=100,
        away_team_club_id=100,
        expected=True,
        description="Club manager can edit when both teams in their club"
    ),
    MatchPermissionScenario(
        id="club_manager_neither_in_club",
        role="club_manager",
        user_team_id=None,
        user_club_id=100,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=200,
        away_team_club_id=300,
        expected=False,
        description="Club manager cannot edit when neither team is in their club"
    ),
    MatchPermissionScenario(
        id="club_manager_no_club_assigned",
        role="club_manager",
        user_team_id=None,
        user_club_id=None,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=100,
        away_team_club_id=200,
        expected=False,
        description="Club manager without club cannot edit any match"
    ),

    # --- TEAM FAN SCENARIOS (should always fail) ---
    MatchPermissionScenario(
        id="team_fan_own_team_home",
        role="team-fan",
        user_team_id=5,
        user_club_id=None,
        permissions=[],
        home_team_id=5,
        away_team_id=10,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Team fan cannot edit even when their team is playing"
    ),
    MatchPermissionScenario(
        id="team_fan_any_match",
        role="team-fan",
        user_team_id=5,
        user_club_id=None,
        permissions=[],
        home_team_id=10,
        away_team_id=20,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Team fan cannot edit any match"
    ),

    # --- REGULAR USER SCENARIOS ---
    MatchPermissionScenario(
        id="user_any_match",
        role="user",
        user_team_id=None,
        user_club_id=None,
        permissions=[],
        home_team_id=1,
        away_team_id=2,
        home_team_club_id=None,
        away_team_club_id=None,
        expected=False,
        description="Regular user cannot edit any match"
    ),
]


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client for authorization tests."""
    return Mock()


@pytest.fixture
def auth_manager(mock_supabase):
    """Create AuthManager with mocked Supabase client."""
    with patch.dict(os.environ, {'SUPABASE_JWT_SECRET': 'test-secret-key-for-testing'}):
        return AuthManager(supabase_client=mock_supabase)


@pytest.mark.unit
@pytest.mark.auth
@pytest.mark.data_driven
@allure.suite("Parameterized Tests")
@allure.sub_suite("Authorization Matrix")
@allure.feature("Security")
@allure.story("Team Management Permissions")
class TestTeamManagementMatrix:
    """
    Comprehensive authorization matrix for team management.

    This single test class covers 13 scenarios across all roles:
    - Admin access (2 scenarios)
    - Team manager access (3 scenarios)
    - Club manager access (4 scenarios)
    - Team fan restrictions (2 scenarios)
    - Regular user restrictions (1 scenario)
    - Service account restrictions (1 scenario)
    """

    @pytest.mark.parametrize(
        "scenario",
        TEAM_MANAGEMENT_SCENARIOS,
        ids=lambda s: s.id
    )
    @allure.severity(allure.severity_level.CRITICAL)
    def test_can_manage_team(
        self,
        auth_manager: AuthManager,
        scenario: TeamPermissionScenario
    ):
        """
        Test team management permissions across all role combinations.

        The test matrix documents business rules:
        - Admins can manage ANY team
        - Team managers can ONLY manage their assigned team
        - Club managers can manage teams within their club
        - Other roles cannot manage teams
        """
        # Arrange
        user_data = {
            "role": scenario.role,
            "team_id": scenario.user_team_id,
            "club_id": scenario.user_club_id,
        }

        # Mock _get_team_club_id to return the target team's club
        with patch.object(
            auth_manager,
            '_get_team_club_id',
            return_value=scenario.target_team_club_id
        ):
            # Act
            result = auth_manager.can_manage_team(
                user_data,
                team_id=scenario.target_team_id
            )

        # Assert
        assert result == scenario.expected, (
            f"\n{'='*60}\n"
            f"SCENARIO: {scenario.id}\n"
            f"{'='*60}\n"
            f"Description: {scenario.description}\n"
            f"\nUser Context:\n"
            f"  - Role: {scenario.role}\n"
            f"  - User's team_id: {scenario.user_team_id}\n"
            f"  - User's club_id: {scenario.user_club_id}\n"
            f"\nTarget:\n"
            f"  - Target team_id: {scenario.target_team_id}\n"
            f"  - Target team's club_id: {scenario.target_team_club_id}\n"
            f"\nResult:\n"
            f"  - Expected can_manage: {scenario.expected}\n"
            f"  - Actual can_manage: {result}\n"
            f"{'='*60}"
        )


@pytest.mark.unit
@pytest.mark.auth
@pytest.mark.data_driven
@allure.suite("Parameterized Tests")
@allure.sub_suite("Authorization Matrix")
@allure.feature("Security")
@allure.story("Match Editing Permissions")
class TestMatchEditingMatrix:
    """
    Comprehensive authorization matrix for match editing.

    This single test class covers 20 scenarios across all roles:
    - Admin access (1 scenario)
    - Service account with/without permissions (4 scenarios)
    - Team manager access (4 scenarios)
    - Club manager access (5 scenarios)
    - Team fan restrictions (2 scenarios)
    - Regular user restrictions (1 scenario)
    """

    @pytest.mark.parametrize(
        "scenario",
        MATCH_EDITING_SCENARIOS,
        ids=lambda s: s.id
    )
    @allure.severity(allure.severity_level.CRITICAL)
    def test_can_edit_match(
        self,
        auth_manager: AuthManager,
        scenario: MatchPermissionScenario
    ):
        """
        Test match editing permissions across all role combinations.

        The test matrix documents business rules:
        - Admins can edit ANY match
        - Service accounts need 'manage_matches' permission
        - Team managers can edit matches involving THEIR team
        - Club managers can edit matches involving ANY team in their club
        - Other roles cannot edit matches
        """
        # Arrange
        user_data = {
            "role": scenario.role,
            "team_id": scenario.user_team_id,
            "club_id": scenario.user_club_id,
            "permissions": scenario.permissions,
        }

        # Mock _get_team_club_id to return appropriate club IDs
        def mock_get_club(team_id):
            if team_id == scenario.home_team_id:
                return scenario.home_team_club_id
            if team_id == scenario.away_team_id:
                return scenario.away_team_club_id
            return None

        with patch.object(
            auth_manager,
            '_get_team_club_id',
            side_effect=mock_get_club
        ):
            # Act
            result = auth_manager.can_edit_match(
                user_data,
                home_team_id=scenario.home_team_id,
                away_team_id=scenario.away_team_id
            )

        # Assert
        assert result == scenario.expected, (
            f"\n{'='*60}\n"
            f"SCENARIO: {scenario.id}\n"
            f"{'='*60}\n"
            f"Description: {scenario.description}\n"
            f"\nUser Context:\n"
            f"  - Role: {scenario.role}\n"
            f"  - User's team_id: {scenario.user_team_id}\n"
            f"  - User's club_id: {scenario.user_club_id}\n"
            f"  - Permissions: {scenario.permissions}\n"
            f"\nMatch:\n"
            f"  - Home team_id: {scenario.home_team_id} (club: {scenario.home_team_club_id})\n"
            f"  - Away team_id: {scenario.away_team_id} (club: {scenario.away_team_club_id})\n"
            f"\nResult:\n"
            f"  - Expected can_edit: {scenario.expected}\n"
            f"  - Actual can_edit: {result}\n"
            f"{'='*60}"
        )


@pytest.mark.unit
@pytest.mark.auth
@allure.suite("Parameterized Tests")
@allure.sub_suite("Authorization Matrix")
@allure.feature("Test Quality")
@allure.story("Matrix Coverage Verification")
class TestPermissionMatrixCoverage:
    """Meta-tests to verify permission matrix completeness."""

    @allure.severity(allure.severity_level.NORMAL)
    def test_all_roles_covered_in_team_management(self):
        """Verify all known roles have team management scenarios."""
        roles_in_scenarios = {s.role for s in TEAM_MANAGEMENT_SCENARIOS}
        expected_roles = {"admin", "team-manager", "club_manager", "team-fan", "user", "service_account"}

        missing = expected_roles - roles_in_scenarios
        assert not missing, f"Missing team management scenarios for roles: {missing}"

    def test_all_roles_covered_in_match_editing(self):
        """Verify all known roles have match editing scenarios."""
        roles_in_scenarios = {s.role for s in MATCH_EDITING_SCENARIOS}
        expected_roles = {"admin", "team-manager", "club_manager", "team-fan", "user", "service_account"}

        missing = expected_roles - roles_in_scenarios
        assert not missing, f"Missing match editing scenarios for roles: {missing}"

    def test_positive_and_negative_scenarios_exist(self):
        """Verify both allowed and denied scenarios exist for each matrix."""
        team_allowed = sum(1 for s in TEAM_MANAGEMENT_SCENARIOS if s.expected)
        team_denied = sum(1 for s in TEAM_MANAGEMENT_SCENARIOS if not s.expected)

        match_allowed = sum(1 for s in MATCH_EDITING_SCENARIOS if s.expected)
        match_denied = sum(1 for s in MATCH_EDITING_SCENARIOS if not s.expected)

        assert team_allowed > 0, "Should have positive team management scenarios"
        assert team_denied > 0, "Should have negative team management scenarios"
        assert match_allowed > 0, "Should have positive match editing scenarios"
        assert match_denied > 0, "Should have negative match editing scenarios"

        # Print coverage summary
        print(f"\nTeam Management Matrix: {team_allowed} allowed, {team_denied} denied")
        print(f"Match Editing Matrix: {match_allowed} allowed, {match_denied} denied")


# ============================================================================
# Documentation Helper
# ============================================================================

def print_permission_matrix():
    """Print the full permission matrix for documentation."""
    print("\n" + "=" * 80)
    print("TEAM MANAGEMENT PERMISSION MATRIX")
    print("=" * 80)
    print(f"{'ID':<35} {'ROLE':<15} {'RESULT':<10} DESCRIPTION")
    print("-" * 80)
    for s in TEAM_MANAGEMENT_SCENARIOS:
        status = "ALLOWED" if s.expected else "DENIED"
        print(f"{s.id:<35} {s.role:<15} {status:<10} {s.description}")

    print("\n" + "=" * 80)
    print("MATCH EDITING PERMISSION MATRIX")
    print("=" * 80)
    print(f"{'ID':<35} {'ROLE':<15} {'RESULT':<10} DESCRIPTION")
    print("-" * 80)
    for s in MATCH_EDITING_SCENARIOS:
        status = "ALLOWED" if s.expected else "DENIED"
        print(f"{s.id:<35} {s.role:<15} {status:<10} {s.description}")


if __name__ == "__main__":
    print_permission_matrix()
