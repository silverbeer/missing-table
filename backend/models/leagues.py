"""
League and division-related Pydantic models.
"""
from datetime import datetime
from pydantic import BaseModel


class League(BaseModel):
    """Model for league data."""
    id: int
    name: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeagueCreate(BaseModel):
    """Model for creating a new league."""
    name: str
    description: str | None = None
    is_active: bool = True


class LeagueUpdate(BaseModel):
    """Model for updating league information."""
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DivisionCreate(BaseModel):
    """Model for creating a new division."""
    name: str
    description: str | None = None
    league_id: int  # Required: divisions must belong to a league


class DivisionUpdate(BaseModel):
    """Model for updating division information."""
    name: str | None = None
    description: str | None = None
    league_id: int | None = None  # Optional for updates

