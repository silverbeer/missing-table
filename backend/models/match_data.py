"""
Match data model for message queue processing.

This model validates match data received from RabbitMQ messages.
It must match the JSON schema defined in docs/08-integrations/match-message-schema.json.

NOTE: This model is intentionally duplicated in match-scraper repo to avoid
cross-repo dependencies. Contract is enforced via JSON schema and tests.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MatchData(BaseModel):
    """
    Match data model - must match match-message-schema.json.

    This is used by Celery workers to validate incoming match messages.
    """

    # Required fields
    home_team: str = Field(..., min_length=1, description="Home team name")
    away_team: str = Field(..., min_length=1, description="Away team name")
    date: date = Field(..., description="Match date")
    season: str = Field(..., min_length=1, description="Season identifier")
    age_group: str = Field(..., min_length=1, description="Age group")
    match_type: str = Field(..., min_length=1, description="Match type")

    # Optional fields
    division: str | None = Field(None, description="Division name")
    score_home: int | None = Field(None, ge=0, description="Home team score")
    score_away: int | None = Field(None, ge=0, description="Away team score")
    status: Literal["scheduled", "completed", "postponed", "cancelled"] | None = Field(
        None, description="Match status"
    )
    match_id: str | None = Field(None, description="External match ID for deduplication")
    location: str | None = Field(None, description="Match location/venue")
    notes: str | None = Field(None, description="Additional notes")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "examples": [
                {
                    "home_team": "Chicago Fire Juniors",
                    "away_team": "Indiana Fire Academy",
                    "date": "2025-10-13",
                    "season": "2024-25",
                    "age_group": "U14",
                    "match_type": "League",
                    "division": "Northeast",
                    "score_home": 2,
                    "score_away": 1,
                    "status": "completed",
                    "match_id": "mlsnext_12345",
                    "location": "Toyota Park",
                }
            ]
        }
