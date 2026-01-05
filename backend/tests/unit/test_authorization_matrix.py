"""
Authorization Matrix Testing - Comprehensive permission coverage.

Tests AuthManager.can_manage_team() and AuthManager.can_edit_match()
using parameterized scenarios that document business rules.

Business Rules:
- admin: Can manage any team, can edit any match
- team-manager: Can manage own team only, can edit matches involving own team
- club_manager: Can manage teams in their club, can edit matches with club teams
- team-fan: Cannot manage any team, cannot edit any match
- service_account: With manage_matches permission can edit any match

Usage:
    pytest tests/unit/test_authorization_matrix.py -v
"""

import os
from unittest.mock import Mock, patch

import pytest

from auth import AuthManager


# ============================================================================
# PERMISSION MATRIX: can_manage_team()
# ============================================================================

TEAM_MANAGEMENT_SCENARIOS = [
    # --- ADMIN SCENARIOS ---
    {
        "id": "admin_any_team",
        "role": "admin",
        "user_team_id": 1,
        "user_club_id": None,
        "target_team_id": 999,
        "target_team_club_id": None,
        "expected": True,
        "description": "Admin can manage any team regardless of affiliation",
    },
    {
        "id": "admin_no_team_assignment",
        "role": "admin",
        "user_team_id": None,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": 10,
        "expected": True,
        "description": "Admin without team assignment can still manage any team",
    },
    # --- TEAM MANAGER SCENARIOS ---
    {
        "id": "team_manager_own_team",
        "role": "team-manager",
        "user_team_id": 5,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": True,
        "description": "Team manager can manage their own team",
    },
    {
        "id": "team_manager_other_team",
        "role": "team-manager",
        "user_team_id": 5,
        "user_club_id": None,
        "target_team_id": 10,
        "target_team_club_id": None,
        "expected": False,
        "description": "Team manager cannot manage a different team",
    },
    {
        "id": "team_manager_no_assignment",
        "role": "team-manager",
        "user_team_id": None,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": False,
        "description": "Team manager without team assignment cannot manage any team",
    },
    # --- CLUB MANAGER SCENARIOS ---
    {
        "id": "club_manager_team_in_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "target_team_id": 5,
        "target_team_club_id": 100,
        "expected": True,
        "description": "Club manager can manage team in their club",
    },
    {
        "id": "club_manager_team_different_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "target_team_id": 5,
        "target_team_club_id": 200,
        "expected": False,
        "description": "Club manager cannot manage team in different club",
    },
    {
        "id": "club_manager_team_no_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": False,
        "description": "Club manager cannot manage team with no club affiliation",
    },
    {
        "id": "club_manager_no_club_assignment",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": 100,
        "expected": False,
        "description": "Club manager without club assignment cannot manage any team",
    },
    # --- TEAM FAN SCENARIOS ---
    {
        "id": "team_fan_own_team",
        "role": "team-fan",
        "user_team_id": 5,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": False,
        "description": "Team fan cannot manage even their own team",
    },
    {
        "id": "team_fan_any_team",
        "role": "team-fan",
        "user_team_id": 5,
        "user_club_id": None,
        "target_team_id": 10,
        "target_team_club_id": None,
        "expected": False,
        "description": "Team fan cannot manage any team",
    },
    # --- REGULAR USER SCENARIOS ---
    {
        "id": "user_any_team",
        "role": "user",
        "user_team_id": None,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": False,
        "description": "Regular user cannot manage any team",
    },
    # --- SERVICE ACCOUNT SCENARIOS ---
    {
        "id": "service_account_any_team",
        "role": "service_account",
        "user_team_id": None,
        "user_club_id": None,
        "target_team_id": 5,
        "target_team_club_id": None,
        "expected": False,
        "description": "Service account cannot manage teams (only matches)",
    },
]


# ============================================================================
# PERMISSION MATRIX: can_edit_match()
# ============================================================================

MATCH_EDITING_SCENARIOS = [
    # --- ADMIN SCENARIOS ---
    {
        "id": "admin_any_match",
        "role": "admin",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": True,
        "description": "Admin can edit any match",
    },
    # --- SERVICE ACCOUNT SCENARIOS ---
    {
        "id": "service_with_manage_matches",
        "role": "service_account",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": ["manage_matches"],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": True,
        "description": "Service account with manage_matches can edit any match",
    },
    {
        "id": "service_with_read_only",
        "role": "service_account",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": ["read_only"],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Service account without manage_matches cannot edit",
    },
    {
        "id": "service_empty_permissions",
        "role": "service_account",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Service account with no permissions cannot edit",
    },
    {
        "id": "service_with_multiple_permissions",
        "role": "service_account",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": ["read_data", "manage_matches", "sync_teams"],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": True,
        "description": "Service account with manage_matches among multiple permissions can edit",
    },
    # --- TEAM MANAGER SCENARIOS ---
    {
        "id": "team_manager_home_team",
        "role": "team-manager",
        "user_team_id": 5,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 5,
        "away_team_id": 10,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": True,
        "description": "Team manager can edit match when their team is home",
    },
    {
        "id": "team_manager_away_team",
        "role": "team-manager",
        "user_team_id": 5,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 10,
        "away_team_id": 5,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": True,
        "description": "Team manager can edit match when their team is away",
    },
    {
        "id": "team_manager_neither_team",
        "role": "team-manager",
        "user_team_id": 5,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 10,
        "away_team_id": 20,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Team manager cannot edit match when neither team is theirs",
    },
    {
        "id": "team_manager_no_team_assigned",
        "role": "team-manager",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 5,
        "away_team_id": 10,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Team manager without team cannot edit any match",
    },
    # --- CLUB MANAGER SCENARIOS ---
    {
        "id": "club_manager_home_in_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": 100,
        "away_team_club_id": 200,
        "expected": True,
        "description": "Club manager can edit when home team is in their club",
    },
    {
        "id": "club_manager_away_in_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": 200,
        "away_team_club_id": 100,
        "expected": True,
        "description": "Club manager can edit when away team is in their club",
    },
    {
        "id": "club_manager_both_in_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": 100,
        "away_team_club_id": 100,
        "expected": True,
        "description": "Club manager can edit when both teams in their club",
    },
    {
        "id": "club_manager_neither_in_club",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": 100,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": 200,
        "away_team_club_id": 300,
        "expected": False,
        "description": "Club manager cannot edit when neither team is in their club",
    },
    {
        "id": "club_manager_no_club_assigned",
        "role": "club_manager",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": 100,
        "away_team_club_id": 200,
        "expected": False,
        "description": "Club manager without club cannot edit any match",
    },
    # --- TEAM FAN SCENARIOS ---
    {
        "id": "team_fan_own_team_home",
        "role": "team-fan",
        "user_team_id": 5,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 5,
        "away_team_id": 10,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Team fan cannot edit even when their team is playing",
    },
    {
        "id": "team_fan_any_match",
        "role": "team-fan",
        "user_team_id": 5,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 10,
        "away_team_id": 20,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Team fan cannot edit any match",
    },
    # --- REGULAR USER SCENARIOS ---
    {
        "id": "user_any_match",
        "role": "user",
        "user_team_id": None,
        "user_club_id": None,
        "permissions": [],
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_club_id": None,
        "away_team_club_id": None,
        "expected": False,
        "description": "Regular user cannot edit any match",
    },
]


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client for authorization tests."""
    return Mock()


@pytest.fixture
def auth_manager(mock_supabase):
    """Create AuthManager with mocked Supabase client."""
    with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": "test-secret-key-for-testing"}):
        return AuthManager(supabase_client=mock_supabase)


@pytest.mark.unit
@pytest.mark.auth
class TestTeamManagementMatrix:
    """Test can_manage_team() across all role combinations."""

    @pytest.mark.parametrize("scenario", TEAM_MANAGEMENT_SCENARIOS, ids=lambda s: s["id"])
    def test_can_manage_team(self, auth_manager: AuthManager, scenario: dict):
        """Test team management permissions."""
        user_data = {
            "role": scenario["role"],
            "team_id": scenario["user_team_id"],
            "club_id": scenario["user_club_id"],
        }

        with patch.object(
            auth_manager, "_get_team_club_id", return_value=scenario["target_team_club_id"]
        ):
            result = auth_manager.can_manage_team(user_data, team_id=scenario["target_team_id"])

        assert result == scenario["expected"], (
            f"FAILED: {scenario['id']}\n"
            f"  {scenario['description']}\n"
            f"  Role: {scenario['role']}, Expected: {scenario['expected']}, Got: {result}"
        )


@pytest.mark.unit
@pytest.mark.auth
class TestMatchEditingMatrix:
    """Test can_edit_match() across all role combinations."""

    @pytest.mark.parametrize("scenario", MATCH_EDITING_SCENARIOS, ids=lambda s: s["id"])
    def test_can_edit_match(self, auth_manager: AuthManager, scenario: dict):
        """Test match editing permissions."""
        user_data = {
            "role": scenario["role"],
            "team_id": scenario["user_team_id"],
            "club_id": scenario["user_club_id"],
            "permissions": scenario["permissions"],
        }

        def mock_get_club(team_id):
            if team_id == scenario["home_team_id"]:
                return scenario["home_team_club_id"]
            if team_id == scenario["away_team_id"]:
                return scenario["away_team_club_id"]
            return None

        with patch.object(auth_manager, "_get_team_club_id", side_effect=mock_get_club):
            result = auth_manager.can_edit_match(
                user_data,
                home_team_id=scenario["home_team_id"],
                away_team_id=scenario["away_team_id"],
            )

        assert result == scenario["expected"], (
            f"FAILED: {scenario['id']}\n"
            f"  {scenario['description']}\n"
            f"  Role: {scenario['role']}, Expected: {scenario['expected']}, Got: {result}"
        )


@pytest.mark.unit
class TestPermissionMatrixCoverage:
    """Verify permission matrix completeness."""

    def test_all_roles_covered_in_team_management(self):
        """Verify all known roles have team management scenarios."""
        roles_in_scenarios = {s["role"] for s in TEAM_MANAGEMENT_SCENARIOS}
        expected_roles = {"admin", "team-manager", "club_manager", "team-fan", "user", "service_account"}
        missing = expected_roles - roles_in_scenarios
        assert not missing, f"Missing team management scenarios for roles: {missing}"

    def test_all_roles_covered_in_match_editing(self):
        """Verify all known roles have match editing scenarios."""
        roles_in_scenarios = {s["role"] for s in MATCH_EDITING_SCENARIOS}
        expected_roles = {"admin", "team-manager", "club_manager", "team-fan", "user", "service_account"}
        missing = expected_roles - roles_in_scenarios
        assert not missing, f"Missing match editing scenarios for roles: {missing}"

    def test_positive_and_negative_scenarios_exist(self):
        """Verify both allowed and denied scenarios exist."""
        team_allowed = sum(1 for s in TEAM_MANAGEMENT_SCENARIOS if s["expected"])
        team_denied = sum(1 for s in TEAM_MANAGEMENT_SCENARIOS if not s["expected"])
        match_allowed = sum(1 for s in MATCH_EDITING_SCENARIOS if s["expected"])
        match_denied = sum(1 for s in MATCH_EDITING_SCENARIOS if not s["expected"])

        assert team_allowed > 0 and team_denied > 0, "Need both positive and negative team scenarios"
        assert match_allowed > 0 and match_denied > 0, "Need both positive and negative match scenarios"
