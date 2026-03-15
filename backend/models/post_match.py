"""
Post-Match Stats Pydantic models.

Models for recording goals, substitutions, and player stats
after a match has been completed.
"""

from pydantic import BaseModel, Field


class PostMatchGoal(BaseModel):
    """Model for recording a post-match goal event."""

    team_id: int = Field(..., description="ID of the team that scored")
    player_id: int | None = Field(None, description="ID of the goal scorer from roster (preferred)")
    player_name: str | None = Field(None, max_length=200, description="Name of goal scorer (when no roster)")
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


class PostMatchCard(BaseModel):
    """Model for recording a post-match card event (yellow or red)."""

    team_id: int = Field(..., description="ID of the team the player belongs to")
    player_id: int | None = Field(None, description="ID of the carded player from roster (preferred)")
    player_name: str | None = Field(None, max_length=200, description="Name of player (when no roster)")
    card_type: str = Field(..., pattern="^(yellow_card|red_card)$", description="Type of card: yellow_card or red_card")
    match_minute: int = Field(..., ge=1, le=130, description="Minute the card was given")
    extra_time: int | None = Field(None, ge=1, description="Stoppage time minutes")
    message: str | None = Field(None, max_length=500, description="Optional description (e.g., reason for card)")


class PlayerStatEntry(BaseModel):
    """Model for a single player's match stats update."""

    player_id: int = Field(..., description="Player ID from roster")
    started: bool = Field(..., description="Whether the player started the match")
    played: bool = Field(..., description="Whether the player participated in the match")
    minutes_played: int = Field(..., ge=0, le=130, description="Total minutes played")
    yellow_cards: int = Field(0, ge=0, le=2, description="Yellow cards received (0-2)")
    red_cards: int = Field(0, ge=0, le=1, description="Red cards received (0-1)")


class BatchPlayerStatsUpdate(BaseModel):
    """Model for batch-updating player stats for a team in a match."""

    players: list[PlayerStatEntry] = Field(..., min_length=1, description="List of player stat entries")
