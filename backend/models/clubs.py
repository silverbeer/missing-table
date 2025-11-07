"""
Pydantic models for clubs and teams data structure.
Used for parsing and validating clubs.json.
"""
from pydantic import BaseModel, Field, field_validator


class TeamData(BaseModel):
    """Model for team data in clubs.json."""

    team_name: str
    league: str
    division: str | None = None
    conference: str | None = None
    age_groups: list[str] | None = Field(default=None)

    @field_validator("league")
    @classmethod
    def validate_league(cls, v: str) -> str:
        """Validate league is a known value."""
        valid_leagues = {"Homegrown", "Academy"}
        if v not in valid_leagues:
            raise ValueError(f"League must be one of {valid_leagues}, got {v}")
        return v

    @property
    def division_or_conference(self) -> str | None:
        """Get division or conference (whichever is set)."""
        return self.division or self.conference

    @property
    def is_complete(self) -> bool:
        """Check if team has all required data (division/conference and age_groups)."""
        return bool(self.division_or_conference and self.age_groups)


class ClubData(BaseModel):
    """Model for club data in clubs.json."""

    club_name: str
    location: str
    website: str
    teams: list[TeamData]
    is_pro_academy: bool = Field(
        default=False,
        description="True if this club is a professional academy (e.g., MLS Pro Academy). All teams in the club inherit this designation."
    )

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str) -> str:
        """Validate website is a URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Website must be a valid URL, got {v}")
        return v


def load_clubs_from_json(clubs_json: list[dict]) -> list[ClubData]:
    """
    Parse clubs.json data into Pydantic models.

    Args:
        clubs_json: Raw JSON data (list of dicts)

    Returns:
        List of validated ClubData models

    Raises:
        ValidationError: If data doesn't match expected structure
    """
    return [ClubData(**club) for club in clubs_json]
