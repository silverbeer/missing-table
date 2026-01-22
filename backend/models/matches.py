"""
Match-related Pydantic models.
"""

from datetime import datetime

from pydantic import BaseModel


class EnhancedMatch(BaseModel):
    """Model for creating or updating a match with full context."""

    match_date: str
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    season_id: int
    age_group_id: int
    match_type_id: int
    division_id: int | None = None
    status: str | None = "scheduled"  # scheduled, played, postponed, cancelled (maps to match_status in DB)
    created_by: str | None = None  # User ID who created the match (for audit trail)
    updated_by: str | None = None  # User ID who last updated the match
    source: str = "manual"  # Source: manual, match-scraper, import
    external_match_id: str | None = None  # External match identifier (e.g., from match-scraper)
    scheduled_kickoff: datetime | None = None  # Scheduled kickoff datetime in UTC


class MatchPatch(BaseModel):
    """Model for partial match updates."""

    home_score: int | None = None
    away_score: int | None = None
    match_status: str | None = None
    match_date: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    season_id: int | None = None
    age_group_id: int | None = None
    match_type_id: int | None = None
    division_id: int | None = None
    status: str | None = None
    external_match_id: str | None = None  # External match identifier
    scheduled_kickoff: datetime | None = None  # Scheduled kickoff datetime in UTC

    class Config:
        # Validation for scores
        @staticmethod
        def validate_score(v):
            if v is not None and v < 0:
                raise ValueError("Score must be non-negative")
            return v


class MatchSubmissionData(BaseModel):
    """
    Match data for async submission to Celery queue.
    This model accepts flexible data from match-scraper.
    """

    home_team: str  # Team name (will be looked up)
    away_team: str  # Team name (will be looked up)
    match_date: str  # ISO format date
    season: str  # Season name (e.g., "2024-25")
    age_group: str | None = None
    division: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    match_status: str = "scheduled"  # scheduled, live, played, postponed, cancelled
    match_type: str | None = None
    location: str | None = None
    external_match_id: str | None = None  # External identifier for deduplication
