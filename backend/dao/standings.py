"""
Pure functions for league standings calculation.

This module contains pure functions with no external dependencies,
making them trivially testable without mocking.

These functions are used by MatchDAO.get_league_table() but can be
unit tested independently.
"""

from collections import defaultdict
from datetime import date
from operator import itemgetter


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


def filter_by_match_types(matches: list[dict], names: set[str] | None) -> list[dict]:
    """
    Keep matches in any of the named competitions. None keeps every one.

    The singular version has no way to ask for "every competition", which is
    why there was no combined table at all (SB-834). None is the pass-through
    rather than a sentinel string, so a caller cannot spell it wrong.
    """
    if names is None:
        return list(matches)
    return [m for m in matches if (m.get("match_type") or {}).get("name") in names]


def teams_in_division(matches: list[dict], division_id: int) -> set[int]:
    """
    The team ids that make up a division's table.

    A team is in the table because it plays matches *in* the division — both
    sides in division X — which for the 2026-2027 data means its League
    matches. Its Flex matches carry the Flex bracket's division_id and would
    never qualify a team for the Homegrown table on their own.
    """
    team_ids: set[int] = set()
    for match in filter_same_division_matches(matches, division_id):
        for side in ("home_team", "away_team"):
            team_id = (match.get(side) or {}).get("id")
            if team_id is not None:
                team_ids.add(team_id)
    return team_ids


def filter_matches_involving(matches: list[dict], team_ids: set[int]) -> list[dict]:
    """Matches with at least one of these teams in them."""
    kept = []
    for match in matches:
        home_id = (match.get("home_team") or {}).get("id")
        away_id = (match.get("away_team") or {}).get("id")
        if home_id in team_ids or away_id in team_ids:
            kept.append(match)
    return kept


def count_outside_table_opponents(matches: list[dict], team_ids: set[int]) -> tuple[int, int]:
    """
    How much of this table is played against teams that are not in it.

    Returns (matches_against_outsiders, distinct_outsiders).

    This is the combined view's denominator, and it is part of the feature
    rather than a footnote. Flex brackets cut across Homegrown divisions, so a
    team's combined points include results against opponents the table does not
    list — that is a record, not a standing, and per CLAUDE.md a cross-team
    statistic ships with its coverage or it does not ship.
    """
    outsiders: set[int] = set()
    count = 0
    for match in matches:
        home_id = (match.get("home_team") or {}).get("id")
        away_id = (match.get("away_team") or {}).get("id")
        for team_id in (home_id, away_id):
            if team_id is not None and team_id not in team_ids:
                outsiders.add(team_id)
                count += 1
                break
    return count, len(outsiders)


def calculate_standings(matches: list[dict], only_team_ids: set[int] | None = None) -> list[dict]:
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

    only_team_ids restricts which teams get a *row*, without discarding the
    match. The combined qualifying table needs exactly that: a team's Flex
    results count towards its points even when the opponent sits outside the
    division, and that opponent must not appear as a row — it has not played
    the rest of the table (SB-834). None means every team gets a row.
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
            "logo_url": None,
            "team_id": None,
            "club_id": None,
        }
    )

    def record(team: dict, goals_for: int, goals_against: int) -> None:
        """Fold one team's side of one result into its row."""
        row = standings[team["name"]]

        if row["team_id"] is None:
            row["team_id"] = team.get("id")

        club = team.get("club") or {}
        if not row["logo_url"]:
            row["logo_url"] = club.get("logo_url")
        if row["club_id"] is None:
            row["club_id"] = club.get("id")

        row["played"] += 1
        row["goals_for"] += goals_for
        row["goals_against"] += goals_against

        if goals_for > goals_against:
            row["wins"] += 1
            row["points"] += 3
        elif goals_for < goals_against:
            row["losses"] += 1
        else:
            row["draws"] += 1
            row["points"] += 1

    def in_table(team: dict) -> bool:
        return only_team_ids is None or team.get("id") in only_team_ids

    for match in matches:
        home = match["home_team"]
        away = match["away_team"]
        home_score = match.get("home_score")
        away_score = match.get("away_score")

        # Skip matches without scores
        if home_score is None or away_score is None:
            continue

        if in_table(home):
            record(home, home_score, away_score)
        if in_table(away):
            record(away, away_score, home_score)

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


def get_team_form(matches: list[dict], last_n: int = 5) -> dict[str, list[str]]:
    """
    Calculate recent form (W/D/L) for each team from completed matches.

    Args:
        matches: List of completed match dicts with scores and match_date
        last_n: Number of recent results to return (default 5)

    Returns:
        Dict mapping team name to list of results, most recent last.
        e.g. {"Northeast IFA": ["W", "L", "D", "W", "W"]}
    """
    # Build per-team results ordered by match_date
    team_results: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for match in matches:
        home_team = match["home_team"]["name"]
        away_team = match["away_team"]["name"]
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        match_date = match.get("match_date", "")

        if home_score is None or away_score is None:
            continue

        if home_score > away_score:
            team_results[home_team].append((match_date, "W"))
            team_results[away_team].append((match_date, "L"))
        elif away_score > home_score:
            team_results[home_team].append((match_date, "L"))
            team_results[away_team].append((match_date, "W"))
        else:
            team_results[home_team].append((match_date, "D"))
            team_results[away_team].append((match_date, "D"))

    # Sort by date and take last N
    form: dict[str, list[str]] = {}
    for team, results in team_results.items():
        results.sort(key=itemgetter(0))
        form[team] = [r for _, r in results[-last_n:]]

    return form


def calculate_position_movement(
    current_matches: list[dict],
    only_team_ids: set[int] | None = None,
) -> dict[str, int]:
    """
    Calculate position change for each team by comparing standings
    with and without the most recent match day's results.

    Args:
        current_matches: All completed matches (with scores and match_date)

    Returns:
        Dict mapping team name to position change (positive = moved up,
        negative = moved down, 0 = unchanged). Teams with no previous
        position (first match day) get 0.
    """
    # Find distinct match dates
    match_dates = set()
    for match in current_matches:
        md = match.get("match_date")
        if md and match.get("home_score") is not None:
            match_dates.add(md)

    if len(match_dates) < 2:
        # Only one match day — no previous standings to compare
        return {}

    latest_date = max(match_dates)

    # Previous standings: exclude the latest match day
    previous_matches = [m for m in current_matches if m.get("match_date") != latest_date]
    previous_table = calculate_standings(previous_matches, only_team_ids)

    # Build position maps (1-indexed)
    previous_positions = {row["team"]: i + 1 for i, row in enumerate(previous_table)}

    current_table = calculate_standings(current_matches, only_team_ids)
    current_positions = {row["team"]: i + 1 for i, row in enumerate(current_table)}

    # Calculate movement: previous - current (positive = moved up)
    movement: dict[str, int] = {}
    for team, current_pos in current_positions.items():
        previous_pos = previous_positions.get(team)
        if previous_pos is None:
            # New team (first match day for them)
            movement[team] = 0
        else:
            movement[team] = previous_pos - current_pos

    return movement


def calculate_standings_with_extras(matches: list[dict], only_team_ids: set[int] | None = None) -> list[dict]:
    """
    Calculate standings enriched with position movement and recent form.

    Wraps calculate_standings() and adds:
        - form: list of last 5 results (e.g. ["W", "D", "L", "W", "W"])
        - position_change: int (positive = moved up, negative = down, 0 = same)

    Args:
        matches: List of completed match dicts

    Returns:
        Same as calculate_standings() but each row also has 'form' and
        'position_change' keys.
    """
    table = calculate_standings(matches, only_team_ids)
    form = get_team_form(matches)
    movement = calculate_position_movement(matches, only_team_ids)

    for row in table:
        team = row["team"]
        row["form"] = form.get(team, [])
        row["position_change"] = movement.get(team, 0)

    return table
