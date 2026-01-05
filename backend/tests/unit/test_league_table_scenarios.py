"""
League Table Calculation Tests - Testing Pure Functions

Tests the pure functions in dao/standings.py using parameterized scenarios.

Business Rules:
1. Points: Win = 3 points, Draw = 1 point, Loss = 0 points
2. Sorting: By points, then goal difference, then goals scored
3. Only completed matches count toward standings
4. Cross-division matches excluded when filtering by division

Usage:
    pytest tests/unit/test_league_table_scenarios.py -v
"""

import pytest

from dao.standings import (
    calculate_standings,
    filter_by_match_type,
    filter_completed_matches,
    filter_same_division_matches,
)


def match(
    home: str,
    away: str,
    home_score: int | None,
    away_score: int | None,
    status: str = "completed",
    match_type: str = "League",
    home_div: int = 1,
    away_div: int = 1,
) -> dict:
    """Helper to create match dicts in DAO format."""
    return {
        "home_team": {"name": home, "division_id": home_div},
        "away_team": {"name": away, "division_id": away_div},
        "match_type": {"name": match_type},
        "home_score": home_score,
        "away_score": away_score,
        "match_status": status,
    }


# ============================================================================
# Test Scenarios - Each documents specific business rules
# ============================================================================

STANDINGS_SCENARIOS = [
    {
        "id": "basic_wins_losses",
        "description": "Basic win/loss point allocation",
        "matches": [
            match("Team A", "Team B", 2, 1),  # A wins
            match("Team A", "Team C", 3, 0),  # A wins
            match("Team B", "Team C", 1, 0),  # B wins
        ],
        "expected": [
            {"team": "Team A", "played": 2, "wins": 2, "draws": 0, "losses": 0, "goals_for": 5, "goals_against": 1, "goal_difference": 4, "points": 6},
            {"team": "Team B", "played": 2, "wins": 1, "draws": 0, "losses": 1, "goals_for": 2, "goals_against": 2, "goal_difference": 0, "points": 3},
            {"team": "Team C", "played": 2, "wins": 0, "draws": 0, "losses": 2, "goals_for": 0, "goals_against": 4, "goal_difference": -4, "points": 0},
        ],
    },
    {
        "id": "draw_points",
        "description": "Draw gives 1 point to each team",
        "matches": [
            match("Team A", "Team B", 1, 1),
            match("Team A", "Team C", 2, 2),
            match("Team B", "Team C", 0, 0),
        ],
        "expected": [
            {"team": "Team A", "played": 2, "wins": 0, "draws": 2, "losses": 0, "goals_for": 3, "goals_against": 3, "goal_difference": 0, "points": 2},
            {"team": "Team C", "played": 2, "wins": 0, "draws": 2, "losses": 0, "goals_for": 2, "goals_against": 2, "goal_difference": 0, "points": 2},
            {"team": "Team B", "played": 2, "wins": 0, "draws": 2, "losses": 0, "goals_for": 1, "goals_against": 1, "goal_difference": 0, "points": 2},
        ],
    },
    {
        "id": "goal_difference_tiebreaker",
        "description": "Equal points sorted by goal difference",
        "matches": [
            match("Team A", "Team B", 4, 0),  # A wins by 4
            match("Team C", "Team D", 1, 0),  # C wins by 1
            match("Team A", "Team C", 1, 1),  # Draw
            match("Team B", "Team D", 1, 1),  # Draw
        ],
        "expected": [
            {"team": "Team A", "played": 2, "wins": 1, "draws": 1, "losses": 0, "goals_for": 5, "goals_against": 1, "goal_difference": 4, "points": 4},
            {"team": "Team C", "played": 2, "wins": 1, "draws": 1, "losses": 0, "goals_for": 2, "goals_against": 1, "goal_difference": 1, "points": 4},
            {"team": "Team D", "played": 2, "wins": 0, "draws": 1, "losses": 1, "goals_for": 1, "goals_against": 2, "goal_difference": -1, "points": 1},
            {"team": "Team B", "played": 2, "wins": 0, "draws": 1, "losses": 1, "goals_for": 1, "goals_against": 5, "goal_difference": -4, "points": 1},
        ],
    },
    {
        "id": "goals_scored_tiebreaker",
        "description": "Equal points and GD, sorted by goals scored",
        "matches": [
            match("Team A", "Team B", 3, 2),  # A wins, scores 3
            match("Team C", "Team D", 4, 3),  # C wins, scores 4
        ],
        "expected": [
            {"team": "Team C", "played": 1, "wins": 1, "draws": 0, "losses": 0, "goals_for": 4, "goals_against": 3, "goal_difference": 1, "points": 3},
            {"team": "Team A", "played": 1, "wins": 1, "draws": 0, "losses": 0, "goals_for": 3, "goals_against": 2, "goal_difference": 1, "points": 3},
            {"team": "Team D", "played": 1, "wins": 0, "draws": 0, "losses": 1, "goals_for": 3, "goals_against": 4, "goal_difference": -1, "points": 0},
            {"team": "Team B", "played": 1, "wins": 0, "draws": 0, "losses": 1, "goals_for": 2, "goals_against": 3, "goal_difference": -1, "points": 0},
        ],
    },
    {
        "id": "empty_table",
        "description": "No matches returns empty table",
        "matches": [],
        "expected": [],
    },
    {
        "id": "single_match",
        "description": "One match creates two team entries",
        "matches": [match("Team A", "Team B", 0, 0)],
        "expected": [
            {"team": "Team A", "played": 1, "wins": 0, "draws": 1, "losses": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0, "points": 1},
            {"team": "Team B", "played": 1, "wins": 0, "draws": 1, "losses": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0, "points": 1},
        ],
    },
    {
        "id": "high_scoring",
        "description": "Large scores handled correctly",
        "matches": [
            match("Team A", "Team B", 9, 0),
            match("Team C", "Team B", 8, 0),
            match("Team A", "Team C", 5, 5),
        ],
        "expected": [
            {"team": "Team A", "played": 2, "wins": 1, "draws": 1, "losses": 0, "goals_for": 14, "goals_against": 5, "goal_difference": 9, "points": 4},
            {"team": "Team C", "played": 2, "wins": 1, "draws": 1, "losses": 0, "goals_for": 13, "goals_against": 5, "goal_difference": 8, "points": 4},
            {"team": "Team B", "played": 2, "wins": 0, "draws": 0, "losses": 2, "goals_for": 0, "goals_against": 17, "goal_difference": -17, "points": 0},
        ],
    },
    {
        "id": "skip_null_scores",
        "description": "Matches without scores are excluded",
        "matches": [
            match("Team A", "Team B", 2, 1),
            match("Team A", "Team C", None, None),  # No scores
            match("Team B", "Team C", 1, None),  # Partial score
        ],
        "expected": [
            {"team": "Team A", "played": 1, "wins": 1, "draws": 0, "losses": 0, "goals_for": 2, "goals_against": 1, "goal_difference": 1, "points": 3},
            {"team": "Team B", "played": 1, "wins": 0, "draws": 0, "losses": 1, "goals_for": 1, "goals_against": 2, "goal_difference": -1, "points": 0},
        ],
    },
]


@pytest.mark.unit
class TestCalculateStandings:
    """Test calculate_standings() pure function."""

    @pytest.mark.parametrize("scenario", STANDINGS_SCENARIOS, ids=lambda s: s["id"])
    def test_standings_scenario(self, scenario: dict):
        """Test standings calculation for various scenarios."""
        result = calculate_standings(scenario["matches"])

        assert len(result) == len(scenario["expected"]), (
            f"FAILED: {scenario['id']} - {scenario['description']}\n"
            f"Expected {len(scenario['expected'])} teams, got {len(result)}"
        )

        for i, expected in enumerate(scenario["expected"]):
            actual = result[i]
            assert actual["team"] == expected["team"], (
                f"Wrong team at position {i + 1}: expected {expected['team']}, got {actual['team']}"
            )
            for key in ["played", "wins", "draws", "losses", "goals_for", "goals_against", "goal_difference", "points"]:
                assert actual[key] == expected[key], (
                    f"Team {expected['team']}, {key}: expected {expected[key]}, got {actual[key]}"
                )


@pytest.mark.unit
class TestFilterCompletedMatches:
    """Test filter_completed_matches() pure function."""

    def test_filters_completed_only(self):
        """Only completed matches are included."""
        matches = [
            match("A", "B", 1, 0, status="completed"),
            match("A", "C", 2, 0, status="scheduled"),
            match("B", "C", 3, 0, status="postponed"),
            match("A", "D", 1, 1, status="completed"),
        ]
        result = filter_completed_matches(matches)
        assert len(result) == 2
        assert all(m["match_status"] == "completed" for m in result)

    def test_excludes_cancelled(self):
        """Cancelled matches are excluded."""
        matches = [
            match("A", "B", 1, 0, status="completed"),
            match("A", "C", 5, 0, status="cancelled"),
        ]
        result = filter_completed_matches(matches)
        assert len(result) == 1


@pytest.mark.unit
class TestFilterSameDivisionMatches:
    """Test filter_same_division_matches() pure function."""

    def test_filters_cross_division(self):
        """Cross-division matches are excluded."""
        matches = [
            match("A", "B", 1, 0, home_div=1, away_div=1),
            match("A", "C", 2, 0, home_div=1, away_div=2),  # Cross-division
            match("C", "D", 1, 1, home_div=2, away_div=2),
        ]
        result = filter_same_division_matches(matches, division_id=1)
        assert len(result) == 1
        assert result[0]["home_team"]["name"] == "A"
        assert result[0]["away_team"]["name"] == "B"


@pytest.mark.unit
class TestFilterByMatchType:
    """Test filter_by_match_type() pure function."""

    def test_filters_by_match_type(self):
        """Only matches with specified type are included."""
        matches = [
            match("A", "B", 1, 0, match_type="League"),
            match("A", "C", 2, 0, match_type="Cup"),
            match("B", "C", 1, 1, match_type="League"),
        ]
        result = filter_by_match_type(matches, "League")
        assert len(result) == 2
        assert all(m["match_type"]["name"] == "League" for m in result)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases."""

    def test_home_and_away_aggregated(self):
        """Stats aggregated across home and away matches."""
        matches = [
            match("Team A", "Team B", 3, 0),
            match("Team B", "Team A", 0, 3),
        ]
        result = calculate_standings(matches)
        team_a = next(t for t in result if t["team"] == "Team A")
        assert team_a["played"] == 2
        assert team_a["wins"] == 2
        assert team_a["goals_for"] == 6
        assert team_a["points"] == 6
