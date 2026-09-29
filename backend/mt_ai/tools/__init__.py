"""Deterministic MT AI tools: typed inputs, typed results, no model calls."""

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.matches import get_upcoming_matches
from mt_ai.tools.schemas import Viewer
from mt_ai.tools.teams import search_teams

__all__ = ["ToolDeps", "Viewer", "get_upcoming_matches", "search_teams"]
