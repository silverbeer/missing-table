"""
Pydantic models for clubs and teams data structure.
Used for parsing and validating clubs.json and API requests.
"""

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator


def club_name_to_slug(name: str) -> str:
    """Convert club name to filename slug: 'Inter Miami CF' -> 'inter-miami-cf'"""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return name


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
    website: str = ""
    logo_url: str = ""
    primary_color: str = ""
    secondary_color: str = ""
    instagram: str = ""
    teams: list[TeamData]
    is_pro_academy: bool = Field(
        default=False,
        description="True if this club is a professional academy (e.g., MLS Pro Academy). "
        "All teams in the club inherit this designation.",
    )

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str) -> str:
        """Validate website is a URL or empty."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"Website must be a valid URL or empty, got {v}")
        return v

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, v: str) -> str:
        """Validate logo_url is a URL or empty."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"logo_url must be a valid URL or empty, got {v}")
        return v

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Validate color is a hex code or empty."""
        import re

        if v and not re.match(r"^#[0-9a-fA-F]{3,8}$", v):
            raise ValueError(f"Color must be a hex code (e.g., #FF0000) or empty, got {v}")
        return v

    @field_validator("instagram")
    @classmethod
    def validate_instagram(cls, v: str) -> str:
        """Validate instagram is a URL or empty."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"Instagram must be a valid URL or empty, got {v}")
        return v


class Club(BaseModel):
    """Model for creating a new club via API."""

    name: str
    city: str
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


class ClubWithTeams(BaseModel):
    """Model for returning a club with its teams."""

    id: int
    name: str
    city: str
    website: str | None = None
    description: str | None = None
    is_active: bool = True
    teams: list[dict] = []  # Teams belonging to this club
    team_count: int = 0  # Number of teams in this club


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
