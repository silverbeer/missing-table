"""
Team-related Pydantic models.
"""
from pydantic import BaseModel, model_validator


class Team(BaseModel):
    """Model for creating a new team."""
    name: str
    city: str
    age_group_ids: list[int]  # Required: at least one age group
    division_id: int  # Required: single division for all age groups (based on location)
    club_id: int | None = None  # FK to clubs table
    academy_team: bool | None = False

    @model_validator(mode='after')
    def validate_team(self):
        """Validate team has at least one age group."""
        if not self.age_group_ids or len(self.age_group_ids) == 0:
            raise ValueError("Team must have at least one age group")
        return self


class TeamUpdate(BaseModel):
    """Model for updating team information."""
    name: str
    city: str
    academy_team: bool | None = False
    club_id: int | None = None


class TeamMatchTypeMapping(BaseModel):
    """Model for team match type participation."""
    match_type_id: int
    age_group_id: int


class TeamMappingCreate(BaseModel):
    """Model for creating team mappings."""
    team_id: int
    age_group_id: int
    division_id: int

