"""
Playoff bracket Pydantic models.
"""

from pydantic import BaseModel


class PlayoffBracketSlot(BaseModel):
    """A single position in the playoff bracket, with denormalized match data."""

    id: int
    league_id: int
    season_id: int
    age_group_id: int
    round: str
    bracket_position: int
    match_id: int | None = None
    home_seed: int | None = None
    away_seed: int | None = None
    home_source_slot_id: int | None = None
    away_source_slot_id: int | None = None
    # Denormalized from linked match
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    match_status: str | None = None
    match_date: str | None = None


class GenerateBracketRequest(BaseModel):
    """Request to generate a playoff bracket from current standings."""

    league_id: int
    season_id: int
    age_group_id: int
    division_a_id: int
    division_b_id: int


class AdvanceWinnerRequest(BaseModel):
    """Request to advance the winner of a completed bracket slot."""

    slot_id: int
