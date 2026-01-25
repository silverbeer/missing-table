"""
Lineup Pydantic models.

Models for match lineup/formation management.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class LineupPositionEntry(BaseModel):
    """A single player-position assignment in a lineup."""

    player_id: int = Field(..., description="ID of the player")
    position: str = Field(..., max_length=10, description="Position code (e.g., GK, LB, ST)")


class LineupSave(BaseModel):
    """Request model for saving a lineup."""

    formation_name: str = Field(
        ...,
        max_length=20,
        description="Formation preset name (e.g., 4-3-3, 4-4-2)",
    )
    positions: list[LineupPositionEntry] = Field(
        default_factory=list,
        description="List of player-position assignments",
    )


class LineupPositionResponse(BaseModel):
    """A position in a lineup response with player details."""

    player_id: int
    position: str
    jersey_number: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None


class LineupResponse(BaseModel):
    """Response model for a lineup."""

    id: int
    match_id: int
    team_id: int
    formation_name: str
    positions: list[LineupPositionResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
