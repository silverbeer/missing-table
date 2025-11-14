"""
Custom Test Assertions

This module provides reusable assertion functions to make tests more readable
and maintain consistency across the test suite.

Usage:
    from tests.utils.assertions import (
        assert_valid_response,
        assert_has_keys,
        assert_valid_team,
        assert_valid_match
    )
    
    # Assert API response is valid
    response = client.get("/api/teams")
    assert_valid_response(response, status_code=200)
    
    # Assert response data has required keys
    assert_has_keys(response.json(), ["id", "name", "city"])
    
    # Assert team data is valid
    team = response.json()[0]
    assert_valid_team(team)
"""

from typing import Any, Dict, List, Optional, Union
from fastapi.testclient import TestClient


# ============================================================================
# HTTP Response Assertions
# ============================================================================

def assert_valid_response(
    response,
    status_code: int = 200,
    content_type: str = "application/json"
):
    """
    Assert that HTTP response is valid.
    
    Args:
        response: HTTP response object
        status_code: Expected status code (default: 200)
        content_type: Expected content type (default: application/json)
    """
    assert response.status_code == status_code, \
        f"Expected status {status_code}, got {response.status_code}. Response: {response.text}"
    
    if content_type:
        assert content_type in response.headers.get("content-type", ""), \
            f"Expected content-type '{content_type}', got '{response.headers.get('content-type')}'"


def assert_error_response(
    response,
    status_code: int,
    error_message: Optional[str] = None
):
    """
    Assert that response is an error response.
    
    Args:
        response: HTTP response object
        status_code: Expected error status code (4xx or 5xx)
        error_message: Expected error message (optional)
    """
    assert response.status_code == status_code, \
        f"Expected error status {status_code}, got {response.status_code}"
    
    if error_message:
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data, \
            f"Error response missing error message. Response: {data}"
        
        error_text = data.get("detail") or data.get("error") or data.get("message")
        assert error_message in str(error_text), \
            f"Expected error message containing '{error_message}', got '{error_text}'"


# ============================================================================
# Data Structure Assertions
# ============================================================================

def assert_has_keys(data: Dict[str, Any], required_keys: List[str]):
    """
    Assert that dictionary has all required keys.
    
    Args:
        data: Dictionary to check
        required_keys: List of required key names
    """
    missing_keys = [key for key in required_keys if key not in data]
    assert not missing_keys, \
        f"Data missing required keys: {missing_keys}. Available keys: {list(data.keys())}"


def assert_is_list(data: Any, min_length: Optional[int] = None, max_length: Optional[int] = None):
    """
    Assert that data is a list with optional length constraints.
    
    Args:
        data: Data to check
        min_length: Minimum list length (optional)
        max_length: Maximum list length (optional)
    """
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    
    if min_length is not None:
        assert len(data) >= min_length, \
            f"Expected list length >= {min_length}, got {len(data)}"
    
    if max_length is not None:
        assert len(data) <= max_length, \
            f"Expected list length <= {max_length}, got {len(data)}"


def assert_is_valid_id(value: Any):
    """Assert that value is a valid ID (positive integer or UUID string)."""
    if isinstance(value, int):
        assert value > 0, f"Expected positive integer ID, got {value}"
    elif isinstance(value, str):
        # Check if it looks like a UUID or positive integer string
        try:
            int_val = int(value)
            assert int_val > 0, f"Expected positive integer ID string, got {value}"
        except ValueError:
            # Assume it's a UUID - just check it's non-empty
            assert len(value) > 0, f"Expected non-empty ID string, got {value}"
    else:
        assert False, f"Expected int or string ID, got {type(value)}: {value}"


# ============================================================================
# Entity-Specific Assertions
# ============================================================================

def assert_valid_team(team: Dict[str, Any], strict: bool = False):
    """
    Assert that team data has valid structure.
    
    Args:
        team: Team dictionary
        strict: If True, require all optional fields
    """
    # Required fields
    required_keys = ["id", "name", "city"]
    assert_has_keys(team, required_keys)
    
    # Validate ID
    assert_is_valid_id(team["id"])
    
    # Validate name and city are non-empty
    assert len(team["name"]) > 0, "Team name cannot be empty"
    assert len(team["city"]) > 0, "Team city cannot be empty"
    
    # Optional fields (check if strict mode)
    if strict:
        optional_keys = ["age_group_id", "division_id", "season_id", "coach", "contact_email"]
        assert_has_keys(team, optional_keys)


def assert_valid_match(match: Dict[str, Any], strict: bool = False):
    """
    Assert that match data has valid structure.
    
    Args:
        match: Match dictionary
        strict: If True, require all optional fields
    """
    # Required fields
    required_keys = ["id", "match_date", "home_team_id", "away_team_id"]
    assert_has_keys(match, required_keys)
    
    # Validate IDs
    assert_is_valid_id(match["id"])
    assert_is_valid_id(match["home_team_id"])
    assert_is_valid_id(match["away_team_id"])
    
    # Home and away teams must be different
    assert match["home_team_id"] != match["away_team_id"], \
        "Home and away teams must be different"
    
    # Validate date format (basic check)
    assert len(match["match_date"]) >= 10, \
        f"Invalid match_date format: {match['match_date']}"
    
    # If scores are present, validate them
    if "home_score" in match and match["home_score"] is not None:
        assert isinstance(match["home_score"], int), "home_score must be integer"
        assert match["home_score"] >= 0, "home_score must be non-negative"
    
    if "away_score" in match and match["away_score"] is not None:
        assert isinstance(match["away_score"], int), "away_score must be integer"
        assert match["away_score"] >= 0, "away_score must be non-negative"


def assert_valid_user(user: Dict[str, Any], strict: bool = False):
    """
    Assert that user data has valid structure.
    
    Args:
        user: User dictionary
        strict: If True, require all optional fields
    """
    # Required fields
    required_keys = ["id", "email"]
    assert_has_keys(user, required_keys)
    
    # Validate ID
    assert_is_valid_id(user["id"])
    
    # Validate email format (basic check)
    assert "@" in user["email"], f"Invalid email format: {user['email']}"
    
    # Validate role if present
    if "role" in user:
        valid_roles = ["admin", "team_manager", "user"]
        assert user["role"] in valid_roles, \
            f"Invalid role: {user['role']}. Must be one of {valid_roles}"


def assert_valid_standings(standings: List[Dict[str, Any]]):
    """
    Assert that standings/league table data has valid structure.
    
    Args:
        standings: List of team standings dictionaries
    """
    assert_is_list(standings, min_length=1)
    
    for team_stats in standings:
        # Required fields for standings
        required_keys = ["team", "played", "wins", "draws", "losses", "points"]
        assert_has_keys(team_stats, required_keys)
        
        # Validate calculations
        played = team_stats["played"]
        wins = team_stats["wins"]
        draws = team_stats["draws"]
        losses = team_stats["losses"]
        points = team_stats["points"]
        
        # Games should add up
        assert played == wins + draws + losses, \
            f"Games don't add up: {played} != {wins} + {draws} + {losses}"
        
        # Points calculation (3 for win, 1 for draw)
        expected_points = wins * 3 + draws
        assert points == expected_points, \
            f"Points calculation wrong: {points} != {expected_points}"


# ============================================================================
# Authentication Assertions
# ============================================================================

def assert_requires_auth(response):
    """Assert that endpoint requires authentication (401 or 403)."""
    assert response.status_code in [401, 403], \
        f"Expected 401 or 403 (auth required), got {response.status_code}"


def assert_forbidden(response):
    """Assert that endpoint returns forbidden (403)."""
    assert response.status_code == 403, \
        f"Expected 403 (forbidden), got {response.status_code}"


def assert_unauthorized(response):
    """Assert that endpoint returns unauthorized (401)."""
    assert response.status_code == 401, \
        f"Expected 401 (unauthorized), got {response.status_code}"


# ============================================================================
# Pagination Assertions
# ============================================================================

def assert_valid_pagination(data: Dict[str, Any]):
    """
    Assert that response includes valid pagination metadata.
    
    Args:
        data: Response data dictionary
    """
    # Check for pagination keys
    pagination_keys = ["items", "total", "page", "per_page"]
    assert_has_keys(data, pagination_keys)
    
    # Validate pagination values
    assert isinstance(data["items"], list), "items must be a list"
    assert isinstance(data["total"], int), "total must be an integer"
    assert data["total"] >= 0, "total must be non-negative"
    assert isinstance(data["page"], int), "page must be an integer"
    assert data["page"] > 0, "page must be positive"
    assert isinstance(data["per_page"], int), "per_page must be an integer"
    assert data["per_page"] > 0, "per_page must be positive"


# ============================================================================
# Utility Functions
# ============================================================================

def assert_date_format(date_str: str, format: str = "%Y-%m-%d"):
    """
    Assert that string is a valid date in the specified format.
    
    Args:
        date_str: Date string to validate
        format: Expected date format (default: YYYY-MM-DD)
    """
    from datetime import datetime
    
    try:
        datetime.strptime(date_str, format)
    except ValueError:
        assert False, f"Invalid date format '{date_str}'. Expected format: {format}"


def assert_all_match(items: List[Any], predicate):
    """
    Assert that all items in list match predicate.
    
    Args:
        items: List of items to check
        predicate: Function that returns True/False for each item
    """
    failures = [item for item in items if not predicate(item)]
    assert not failures, \
        f"{len(failures)} items failed predicate. First failure: {failures[0] if failures else None}"
