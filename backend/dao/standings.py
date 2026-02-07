"""
Pure functions for league standings calculation.

This module contains pure functions with no external dependencies,
making them trivially testable without mocking.

These functions are used by MatchDAO.get_league_table() but can be
unit tested independently.
"""

from collections import defaultdict
from datetime import date


def filter_completed_matches(matches: list[dict]) -> list[dict]:
    """
    Filter matches to only include completed ones.

    Uses match_status field if available, otherwise falls back to
    date-based logic for backwards compatibility.

    Args:
        matches: List of match dictionaries from database

    Returns:
        List of completed matches only
    """
    played_matches = []
    for match in matches:
        match_status = match.get("match_status")
        if match_status:
            # Use match_status field if available
            if match_status in ("completed", "forfeit"):
                played_matches.append(match)
        else:
            # Fallback to date-based logic for backwards compatibility
            match_date_str = match.get("match_date")
            if match_date_str:
                match_date = date.fromisoformat(match_date_str)
                if match_date <= date.today():
                    played_matches.append(match)
    return played_matches


def filter_same_division_matches(matches: list[dict], division_id: int) -> list[dict]:
    """
    Filter matches to only include those where both teams are in the same division.

    Args:
        matches: List of match dictionaries
        division_id: Division ID to filter by

    Returns:
        List of matches where both teams are in the specified division
    """
    same_division_matches = []
    for match in matches:
        home_div_id = match.get("home_team", {}).get("division_id")
        away_div_id = match.get("away_team", {}).get("division_id")

        # Only include if both teams are in the requested division
        if home_div_id == division_id and away_div_id == division_id:
            same_division_matches.append(match)

    return same_division_matches


def filter_by_match_type(matches: list[dict], match_type: str) -> list[dict]:
    """
    Filter matches by match type name.

    Args:
        matches: List of match dictionaries
        match_type: Match type name to filter by (e.g., "League")

    Returns:
        List of matches with the specified match type
    """
    return [m for m in matches if m.get("match_type", {}).get("name") == match_type]


def calculate_standings(matches: list[dict]) -> list[dict]:
    """
    Calculate league standings from a list of completed matches.

    This is a pure function with no external dependencies.
    It expects matches that have already been filtered to only include
    completed matches with scores.

    Args:
        matches: List of match dictionaries, each containing:
            - home_team: dict with "name" key
            - away_team: dict with "name" key
            - home_score: int or None
            - away_score: int or None

    Returns:
        List of team standings sorted by:
        1. Points (descending)
        2. Goal difference (descending)
        3. Goals scored (descending)

        Each standing contains:
        - team: Team name
        - played: Matches played
        - wins: Number of wins
        - draws: Number of draws
        - losses: Number of losses
        - goals_for: Goals scored
        - goals_against: Goals conceded
        - goal_difference: goals_for - goals_against
        - points: Total points (3 for win, 1 for draw)

    Business Rules:
        - Win = 3 points
        - Draw = 1 point for each team
        - Loss = 0 points
        - Matches without scores are skipped
    """
    standings = defaultdict(
        lambda: {
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
        }
    )

    for match in matches:
        home_team = match["home_team"]["name"]
        away_team = match["away_team"]["name"]
        home_score = match.get("home_score")
        away_score = match.get("away_score")

        # Skip matches without scores
        if home_score is None or away_score is None:
            continue

        # Update played count
        standings[home_team]["played"] += 1
        standings[away_team]["played"] += 1

        # Update goals
        standings[home_team]["goals_for"] += home_score
        standings[home_team]["goals_against"] += away_score
        standings[away_team]["goals_for"] += away_score
        standings[away_team]["goals_against"] += home_score

        # Update wins/draws/losses and points
        if home_score > away_score:
            # Home win
            standings[home_team]["wins"] += 1
            standings[home_team]["points"] += 3
            standings[away_team]["losses"] += 1
        elif away_score > home_score:
            # Away win
            standings[away_team]["wins"] += 1
            standings[away_team]["points"] += 3
            standings[home_team]["losses"] += 1
        else:
            # Draw
            standings[home_team]["draws"] += 1
            standings[away_team]["draws"] += 1
            standings[home_team]["points"] += 1
            standings[away_team]["points"] += 1

    # Convert to list and calculate goal difference
    table = []
    for team, stats in standings.items():
        stats["goal_difference"] = stats["goals_for"] - stats["goals_against"]
        stats["team"] = team
        table.append(stats)

    # Sort by points, goal difference, goals scored (all descending)
    table.sort(
        key=lambda x: (x["points"], x["goal_difference"], x["goals_for"]),
        reverse=True,
    )

    return table
