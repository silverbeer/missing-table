"""
Season and age group-related Pydantic models.
"""

from pydantic import BaseModel


class SeasonCreate(BaseModel):
    """Model for creating a new season."""

    name: str
    start_date: str
    end_date: str


class SeasonUpdate(BaseModel):
    """Model for updating season information."""

    name: str
    start_date: str
    end_date: str


class AgeGroupCreate(BaseModel):
    """Model for creating a new age group."""

    name: str


class AgeGroupUpdate(BaseModel):
    """Model for updating age group information."""

    name: str
