"""Deterministic MT AI tools: typed inputs, typed results, no model calls."""

from mt_ai.tools.deps import ToolDeps
from mt_ai.tools.divisions import list_divisions
from mt_ai.tools.live import get_live_match
from mt_ai.tools.matches import get_upcoming_matches
from mt_ai.tools.results import get_recent_results
from mt_ai.tools.schemas import Viewer
from mt_ai.tools.standings import get_standings
from mt_ai.tools.teams import search_teams

__all__ = [
    "ToolDeps",
    "Viewer",
    "get_live_match",
    "get_recent_results",
    "get_standings",
    "get_upcoming_matches",
    "list_divisions",
    "search_teams",
]
