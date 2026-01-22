"""
Live Match Pydantic models.

Models for managing live match state, clock, and events.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class LiveMatchClock(BaseModel):
    """Model for clock management actions during a live match."""

    action: str = Field(
        ...,
        description="Clock action: start_first_half, start_halftime, etc.",
    )
    half_duration: int | None = Field(
        None,
        ge=20,
        le=60,
        description="Duration of each half in minutes (only for start_first_half)",
    )

    @property
    def valid_actions(self) -> list[str]:
        return ["start_first_half", "start_halftime", "start_second_half", "end_match"]


class GoalEvent(BaseModel):
    """Model for recording a goal event."""

    team_id: int = Field(..., description="ID of the team that scored")
    player_name: str | None = Field(None, max_length=200, description="Name of the goal scorer (legacy)")
    player_id: int | None = Field(None, description="ID of the goal scorer from roster (preferred)")
    message: str | None = Field(None, max_length=500, description="Optional description")


class MessageEvent(BaseModel):
    """Model for posting a chat message."""

    message: str = Field(..., min_length=1, max_length=500, description="Message content")


class MatchEventResponse(BaseModel):
    """Response model for a match event."""

    id: int
    match_id: int
    event_type: str
    team_id: int | None = None
    player_name: str | None = None
    message: str
    created_by: str | None = None
    created_by_username: str | None = None
    created_at: datetime
    is_deleted: bool = False


class LiveMatchState(BaseModel):
    """Full live match state returned to clients."""

    match_id: int
    match_status: str
    home_score: int | None = None
    away_score: int | None = None

    # Clock timestamps
    kickoff_time: datetime | None = None
    halftime_start: datetime | None = None
    second_half_start: datetime | None = None
    match_end_time: datetime | None = None
    half_duration: int = 45  # Minutes per half (default 45 for 90-min games)

    # Team info
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str

    # Match metadata
    match_date: str
    age_group_name: str | None = None
    match_type_name: str | None = None
    division_name: str | None = None

    # Recent events (last N)
    recent_events: list[MatchEventResponse] = []


class LiveMatchSummary(BaseModel):
    """Summary info for the live matches list (for tab polling)."""

    match_id: int
    match_status: str
    home_team_name: str
    away_team_name: str
    home_score: int | None = None
    away_score: int | None = None
    kickoff_time: datetime | None = None
    match_date: str
