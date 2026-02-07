"""
Playoff bracket Pydantic models.
"""

from pydantic import BaseModel


class BracketTierConfig(BaseModel):
    """Configuration for a single bracket tier."""

    name: str  # e.g., "Gold", "Silver"
    start_position: int  # 1 for positions 1-4, 5 for positions 5-8
    end_position: int  # 4 for positions 1-4, 8 for positions 5-8


class PlayoffBracketSlot(BaseModel):
    """A single position in the playoff bracket, with denormalized match data."""

    id: int
    league_id: int
    season_id: int
    age_group_id: int
    round: str
    bracket_position: int
    bracket_tier: str | None = None
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
    scheduled_kickoff: str | None = None


class GenerateBracketRequest(BaseModel):
    """Request to generate a playoff bracket from current standings."""

    league_id: int
    season_id: int
    age_group_id: int
    division_a_id: int
    division_b_id: int
    start_date: str  # ISO date string for QF matches (e.g., "2026-02-15")
    tiers: list[BracketTierConfig]  # e.g., [{"name": "Gold", ...}, ...]


class AdvanceWinnerRequest(BaseModel):
    """Request to advance the winner of a completed bracket slot."""

    slot_id: int


class ForfeitMatchRequest(BaseModel):
    """Request to declare a forfeit on a playoff match."""

    slot_id: int
    forfeit_team_id: int
