"""
Roster-related Pydantic models for player roster management.
"""

from pydantic import BaseModel, Field


class RosterPlayerCreate(BaseModel):
    """Model for creating a single roster entry."""

    jersey_number: int = Field(..., ge=1, le=99, description="Jersey number (1-99)")
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    positions: list[str] | None = None
    season_id: int


class RosterPlayerUpdate(BaseModel):
    """Model for updating a roster entry's name or positions."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    positions: list[str] | None = None


class JerseyNumberUpdate(BaseModel):
    """Model for changing a player's jersey number."""

    new_number: int = Field(..., ge=1, le=99, description="New jersey number (1-99)")


class BulkRosterPlayer(BaseModel):
    """Single player entry for bulk roster creation."""

    jersey_number: int = Field(..., ge=1, le=99)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    positions: list[str] | None = None


class BulkRosterCreate(BaseModel):
    """Model for bulk creating roster entries."""

    season_id: int
    players: list[BulkRosterPlayer] = Field(..., min_length=1)


class RenumberEntry(BaseModel):
    """Single entry for bulk renumber operation."""

    player_id: int
    new_number: int = Field(..., ge=1, le=99)


class BulkRenumberRequest(BaseModel):
    """Model for bulk renumbering players."""

    changes: list[RenumberEntry] = Field(..., min_length=1)


class RosterPlayerResponse(BaseModel):
    """Response model for a roster player."""

    id: int
    team_id: int
    season_id: int
    jersey_number: int
    first_name: str | None = None
    last_name: str | None = None
    display_name: str  # Computed: full name or "#23"
    user_profile_id: str | None = None
    has_account: bool
    positions: list[str] | None = None
    is_active: bool

    class Config:
        """Pydantic config."""

        from_attributes = True
