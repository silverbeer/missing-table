"""
Validation Tasks

Tasks for validating match data before processing.
These ensure data quality and prevent invalid data from entering the database.
"""

from typing import Dict, Any, List
from datetime import datetime
from celery_app import app
from logging_config import get_logger

logger = get_logger(__name__)


@app.task(name='celery_tasks.validation_tasks.validate_match_data')
def validate_match_data(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate match data structure and contents.

    Checks:
    - Required fields are present
    - Data types are correct
    - Values are within acceptable ranges
    - Dates are valid
    - Team names are not empty

    Args:
        match_data: Dictionary containing match information

    Returns:
        Dict containing:
        - valid: bool - Whether the data is valid
        - errors: List[str] - List of validation errors (empty if valid)
        - warnings: List[str] - List of warnings (data is still valid)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Required fields
    required_fields = ['home_team', 'away_team', 'match_date', 'season']
    for field in required_fields:
        if field not in match_data or not match_data[field]:
            errors.append(f"Missing required field: {field}")

    # If required fields are missing, return early
    if errors:
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # Validate team names
    home_team = match_data['home_team']
    away_team = match_data['away_team']

    if not isinstance(home_team, str) or len(home_team.strip()) == 0:
        errors.append("home_team must be a non-empty string")

    if not isinstance(away_team, str) or len(away_team.strip()) == 0:
        errors.append("away_team must be a non-empty string")

    if home_team == away_team:
        errors.append("home_team and away_team cannot be the same")

    # Validate date
    try:
        match_date = match_data['match_date']
        if isinstance(match_date, str):
            # Try to parse ISO format date
            datetime.fromisoformat(match_date.replace('Z', '+00:00'))
        elif not isinstance(match_date, datetime):
            errors.append("match_date must be a string in ISO format or datetime object")
    except (ValueError, AttributeError) as e:
        errors.append(f"Invalid match_date format: {e}")

    # Validate scores (if provided)
    if 'home_score' in match_data and match_data['home_score'] is not None:
        try:
            score = int(match_data['home_score'])
            if score < 0:
                errors.append("home_score cannot be negative")
        except (ValueError, TypeError):
            errors.append("home_score must be an integer")

    if 'away_score' in match_data and match_data['away_score'] is not None:
        try:
            score = int(match_data['away_score'])
            if score < 0:
                errors.append("away_score cannot be negative")
        except (ValueError, TypeError):
            errors.append("away_score must be an integer")

    # Validate match status
    valid_statuses = ['scheduled', 'live', 'completed', 'cancelled', 'postponed']
    if 'match_status' in match_data:
        status = match_data['match_status']
        if status and status not in valid_statuses:
            warnings.append(f"Unusual match_status: {status}. Expected one of: {valid_statuses}")

    # Validate season format
    season = match_data['season']
    if not isinstance(season, str):
        errors.append("season must be a string")
    elif len(season) < 4:
        warnings.append(f"Unusual season format: {season}")

    # Log validation result with structured data
    if errors:
        logger.warning(
            "match_validation_failed",
            home_team=home_team,
            away_team=away_team,
            errors=errors
        )
    elif warnings:
        logger.info(
            "match_validation_warning",
            home_team=home_team,
            away_team=away_team,
            warnings=warnings
        )
    else:
        logger.debug(
            "match_validation_passed",
            home_team=home_team,
            away_team=away_team
        )

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }
