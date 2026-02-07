"""
Post-Match Stats Pydantic models.

Models for recording goals, substitutions, and player stats
after a match has been completed.
"""

from pydantic import BaseModel, Field


class PostMatchGoal(BaseModel):
    """Model for recording a post-match goal event."""

    team_id: int = Field(..., description="ID of the team that scored")
    player_id: int = Field(..., description="ID of the goal scorer from roster")
    match_minute: int = Field(..., ge=1, le=130, description="Minute the goal was scored")
    extra_time: int | None = Field(None, ge=1, description="Stoppage time minutes (e.g., 3 for 45+3)")
    message: str | None = Field(None, max_length=500, description="Optional goal description")


class PostMatchSubstitution(BaseModel):
    """Model for recording a post-match substitution event."""

    team_id: int = Field(..., description="ID of the team making the substitution")
    player_in_id: int = Field(..., description="ID of the player coming on")
    player_out_id: int = Field(..., description="ID of the player coming off")
    match_minute: int = Field(..., ge=1, le=130, description="Minute the substitution occurred")
    extra_time: int | None = Field(None, ge=1, description="Stoppage time minutes")


class PlayerStatEntry(BaseModel):
    """Model for a single player's match stats update."""

    player_id: int = Field(..., description="Player ID from roster")
    started: bool = Field(..., description="Whether the player started the match")
    minutes_played: int = Field(..., ge=0, le=130, description="Total minutes played")


class BatchPlayerStatsUpdate(BaseModel):
    """Model for batch-updating player stats for a team in a match."""

    players: list[PlayerStatEntry] = Field(..., min_length=1, description="List of player stat entries")
