"""
League Table Calculation Scenario Tests

This module tests the league table/standings calculation logic using
scenario-based parameterization. Each scenario represents a real-world
situation with documented business rules.

For qualityplaybook.dev: Demonstrates how parameterized tests can serve as
living documentation for complex business logic. Each scenario explicitly
documents which business rules it validates.

Business Rules Documented:
1. Points: Win = 3 points, Draw = 1 point, Loss = 0 points
2. Sorting: Points (desc) > Goal Difference (desc) > Goals For (desc)
3. Only completed matches count toward standings
4. Matches without scores are excluded
5. Cross-division matches are excluded when filtering by division

Usage:
    pytest tests/unit/test_league_table_scenarios.py -v
    pytest tests/unit/test_league_table_scenarios.py -k "tiebreaker" -v
    pytest tests/unit/test_league_table_scenarios.py -k "exclude" -v
"""

import pytest
import allure
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from collections import defaultdict


@dataclass
class MatchData:
    """Represents a match for test scenarios."""
    home_team: str
    away_team: str
    home_score: Optional[int]
    away_score: Optional[int]
    match_status: str = "completed"
    match_type_name: str = "League"
    home_team_division_id: int = 1
    away_team_division_id: int = 1


@dataclass
class ExpectedStanding:
    """Expected standings result for a team."""
    team: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    position: int  # 1-based position in table


@dataclass
class LeagueTableScenario:
    """Complete test scenario for league table calculation."""
    id: str
    description: str
    matches: List[MatchData]
    expected_standings: List[ExpectedStanding]
    filter_division_id: Optional[int] = None
    filter_match_type: str = "League"
    business_rules_tested: List[str] = field(default_factory=list)


# ============================================================================
# LEAGUE TABLE SCENARIOS
# ============================================================================

LEAGUE_TABLE_SCENARIOS = [
    # Scenario 1: Basic standings calculation
    LeagueTableScenario(
        id="basic_standings",
        description="Basic 3-team league with clear winner",
        business_rules_tested=[
            "3 points for win",
            "0 points for loss",
            "Goals for/against tracking",
            "Correct position ordering"
        ],
        matches=[
            MatchData("Team A", "Team B", 2, 1),  # A wins
            MatchData("Team A", "Team C", 3, 0),  # A wins
            MatchData("Team B", "Team C", 1, 0),  # B wins
        ],
        expected_standings=[
            ExpectedStanding("Team A", 2, 2, 0, 0, 5, 1, 4, 6, 1),
            ExpectedStanding("Team B", 2, 1, 0, 1, 2, 2, 0, 3, 2),
            ExpectedStanding("Team C", 2, 0, 0, 2, 0, 4, -4, 0, 3),
        ]
    ),

    # Scenario 2: Draw handling
    LeagueTableScenario(
        id="draw_points",
        description="Verify draws award 1 point to each team",
        business_rules_tested=[
            "1 point for draw",
            "Draw increments both teams' draw count",
            "Draw does not affect wins/losses",
            "Goals scored tiebreaker applies to draws too"
        ],
        matches=[
            MatchData("Team A", "Team B", 1, 1),  # Draw
            MatchData("Team A", "Team C", 2, 2),  # Draw
            MatchData("Team B", "Team C", 0, 0),  # Draw
        ],
        # All teams have 2 pts, 0 GD, sorted by goals_for: A(3) > C(2) > B(1)
        expected_standings=[
            ExpectedStanding("Team A", 2, 0, 2, 0, 3, 3, 0, 2, 1),  # 3 GF
            ExpectedStanding("Team C", 2, 0, 2, 0, 2, 2, 0, 2, 2),  # 2 GF
            ExpectedStanding("Team B", 2, 0, 2, 0, 1, 1, 0, 2, 3),  # 1 GF
        ]
    ),

    # Scenario 3: Goal difference tiebreaker
    LeagueTableScenario(
        id="goal_difference_tiebreaker",
        description="Teams with equal points sorted by goal difference",
        business_rules_tested=[
            "Goal difference as primary tiebreaker",
            "GD calculated as goals_for - goals_against",
            "Higher GD ranks higher"
        ],
        matches=[
            MatchData("Team A", "Team B", 4, 0),  # A wins by 4
            MatchData("Team C", "Team D", 1, 0),  # C wins by 1
            MatchData("Team B", "Team C", 1, 1),  # Draw
            MatchData("Team A", "Team D", 1, 1),  # Draw
        ],
        expected_standings=[
            ExpectedStanding("Team A", 2, 1, 1, 0, 5, 1, 4, 4, 1),
            ExpectedStanding("Team C", 2, 1, 1, 0, 2, 1, 1, 4, 2),
            ExpectedStanding("Team D", 2, 0, 1, 1, 1, 2, -1, 1, 3),
            ExpectedStanding("Team B", 2, 0, 1, 1, 1, 5, -4, 1, 4),
        ]
    ),

    # Scenario 4: Goals scored as secondary tiebreaker
    LeagueTableScenario(
        id="goals_scored_tiebreaker",
        description="Equal points and GD, sorted by goals scored",
        business_rules_tested=[
            "Goals scored as secondary tiebreaker",
            "Higher goals scored ranks higher when points and GD equal"
        ],
        matches=[
            MatchData("Team A", "Team B", 3, 2),  # A wins, scores 3
            MatchData("Team C", "Team D", 4, 3),  # C wins, scores 4
        ],
        expected_standings=[
            ExpectedStanding("Team C", 1, 1, 0, 0, 4, 3, 1, 3, 1),
            ExpectedStanding("Team A", 1, 1, 0, 0, 3, 2, 1, 3, 2),
            ExpectedStanding("Team D", 1, 0, 0, 1, 3, 4, -1, 0, 3),
            ExpectedStanding("Team B", 1, 0, 0, 1, 2, 3, -1, 0, 4),
        ]
    ),

    # Scenario 5: Scheduled matches excluded
    LeagueTableScenario(
        id="exclude_scheduled",
        description="Scheduled (future) matches don't count",
        business_rules_tested=[
            "Only completed matches count",
            "Scheduled matches with scores are still excluded",
            "match_status field is respected"
        ],
        matches=[
            MatchData("Team A", "Team B", 2, 0, match_status="completed"),
            MatchData("Team A", "Team C", 3, 0, match_status="scheduled"),
        ],
        expected_standings=[
            ExpectedStanding("Team A", 1, 1, 0, 0, 2, 0, 2, 3, 1),
            ExpectedStanding("Team B", 1, 0, 0, 1, 0, 2, -2, 0, 2),
        ]
    ),

    # Scenario 6: Postponed matches excluded
    LeagueTableScenario(
        id="exclude_postponed",
        description="Postponed matches don't affect standings",
        business_rules_tested=[
            "Postponed status excludes match",
            "Even with scores, postponed matches are excluded"
        ],
        matches=[
            MatchData("Team A", "Team B", 1, 0, match_status="completed"),
            MatchData("Team B", "Team C", 5, 0, match_status="postponed"),
        ],
        expected_standings=[
            ExpectedStanding("Team A", 1, 1, 0, 0, 1, 0, 1, 3, 1),
            ExpectedStanding("Team B", 1, 0, 0, 1, 0, 1, -1, 0, 2),
        ]
    ),

    # Scenario 7: Matches without scores excluded
    LeagueTableScenario(
        id="exclude_no_scores",
        description="Completed matches without scores are excluded",
        business_rules_tested=[
            "Null scores exclude match from calculation",
            "Both scores must be present"
        ],
        matches=[
            MatchData("Team A", "Team B", 2, 1, match_status="completed"),
            MatchData("Team A", "Team C", None, None, match_status="completed"),
            MatchData("Team B", "Team C", 1, None, match_status="completed"),
        ],
        expected_standings=[
            ExpectedStanding("Team A", 1, 1, 0, 0, 2, 1, 1, 3, 1),
            ExpectedStanding("Team B", 1, 0, 0, 1, 1, 2, -1, 0, 2),
        ]
    ),

    # Scenario 8: Empty table (no matches)
    LeagueTableScenario(
        id="empty_table",
        description="League with no completed matches returns empty table",
        business_rules_tested=[
            "Empty input returns empty table",
            "No errors on empty data"
        ],
        matches=[],
        expected_standings=[]
    ),

    # Scenario 9: Single team, one match
    LeagueTableScenario(
        id="single_match",
        description="Minimum case: one completed match",
        business_rules_tested=[
            "Handles minimum data correctly",
            "Both teams appear in standings"
        ],
        matches=[
            MatchData("Team A", "Team B", 0, 0),  # Draw
        ],
        expected_standings=[
            ExpectedStanding("Team A", 1, 0, 1, 0, 0, 0, 0, 1, 1),
            ExpectedStanding("Team B", 1, 0, 1, 0, 0, 0, 0, 1, 2),
        ]
    ),

    # Scenario 10: Cross-division matches filtered
    LeagueTableScenario(
        id="cross_division_filter",
        description="Cross-division matches excluded when filtering by division",
        business_rules_tested=[
            "Division filter excludes cross-division matches",
            "Both teams must be in the same division"
        ],
        filter_division_id=1,
        matches=[
            MatchData("Team A", "Team B", 2, 0,
                      home_team_division_id=1, away_team_division_id=1),
            MatchData("Team A", "Team C", 3, 0,
                      home_team_division_id=1, away_team_division_id=2),
        ],
        expected_standings=[
            ExpectedStanding("Team A", 1, 1, 0, 0, 2, 0, 2, 3, 1),
            ExpectedStanding("Team B", 1, 0, 0, 1, 0, 2, -2, 0, 2),
        ]
    ),

    # Scenario 11: High-scoring thriller
    LeagueTableScenario(
        id="high_scoring",
        description="High-scoring matches calculated correctly",
        business_rules_tested=[
            "Large scores handled correctly",
            "Goal difference can be large positive or negative"
        ],
        matches=[
            MatchData("Team A", "Team B", 9, 0),
            MatchData("Team B", "Team C", 0, 8),
            MatchData("Team A", "Team C", 5, 5),  # Draw
        ],
        expected_standings=[
            ExpectedStanding("Team A", 2, 1, 1, 0, 14, 5, 9, 4, 1),
            ExpectedStanding("Team C", 2, 1, 1, 0, 13, 5, 8, 4, 2),
            ExpectedStanding("Team B", 2, 0, 0, 2, 0, 17, -17, 0, 3),
        ]
    ),

    # Scenario 12: Perfect season
    LeagueTableScenario(
        id="perfect_season",
        description="Team wins all matches (invincible)",
        business_rules_tested=[
            "Maximum points per match is 3",
            "Perfect record tracking"
        ],
        matches=[
            MatchData("Team A", "Team B", 1, 0),
            MatchData("Team A", "Team C", 1, 0),
            MatchData("Team A", "Team D", 1, 0),
        ],
        expected_standings=[
            ExpectedStanding("Team A", 3, 3, 0, 0, 3, 0, 3, 9, 1),
            ExpectedStanding("Team B", 1, 0, 0, 1, 0, 1, -1, 0, 2),
            ExpectedStanding("Team C", 1, 0, 0, 1, 0, 1, -1, 0, 3),
            ExpectedStanding("Team D", 1, 0, 0, 1, 0, 1, -1, 0, 4),
        ]
    ),
]


def calculate_league_table(
    matches: List[MatchData],
    filter_division_id: Optional[int] = None,
    filter_match_type: str = "League"
) -> List[Dict[str, Any]]:
    """
    Calculate league table from match data.

    This is a standalone implementation matching the logic in
    backend/dao/match_dao.py get_league_table() for unit testing.

    Args:
        matches: List of match data
        filter_division_id: Optional division filter
        filter_match_type: Match type to include (default: League)

    Returns:
        Sorted list of team standings
    """
    standings = defaultdict(lambda: {
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    })

    for match in matches:
        # Filter by match type
        if match.match_type_name != filter_match_type:
            continue

        # Filter by status (only completed)
        if match.match_status != "completed":
            continue

        # Filter by division (both teams must be in division)
        if filter_division_id is not None:
            if (match.home_team_division_id != filter_division_id or
                    match.away_team_division_id != filter_division_id):
                continue

        # Skip matches without scores
        if match.home_score is None or match.away_score is None:
            continue

        home_team = match.home_team
        away_team = match.away_team
        home_score = match.home_score
        away_score = match.away_score

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
        reverse=True
    )

    return table


@pytest.mark.unit
@pytest.mark.standings
@pytest.mark.data_driven
@allure.suite("Parameterized Tests")
@allure.sub_suite("League Table Scenarios")
@allure.feature("Business Logic")
@allure.story("Standings Calculation")
class TestLeagueTableScenarios:
    """
    Scenario-based league table calculation tests.

    Each scenario documents specific business rules through
    real-world examples. The scenario descriptions serve as
    living documentation of the standings calculation logic.

    For qualityplaybook.dev: This pattern makes business rules
    explicit and testable. Stakeholders can understand the logic
    by reading the scenario descriptions.
    """

    @pytest.mark.parametrize(
        "scenario",
        LEAGUE_TABLE_SCENARIOS,
        ids=lambda s: s.id
    )
    @allure.severity(allure.severity_level.CRITICAL)
    def test_league_table_scenario(self, scenario: LeagueTableScenario):
        """
        Test league table calculation against expected standings.

        This test covers 12 scenarios including:
        - Basic point calculation
        - Tiebreaker logic (GD, goals scored)
        - Match status filtering (completed, scheduled, postponed)
        - Division filtering
        - Edge cases (empty, single match, high scores)
        """
        # Act
        result = calculate_league_table(
            matches=scenario.matches,
            filter_division_id=scenario.filter_division_id,
            filter_match_type=scenario.filter_match_type
        )

        # Assert - verify table structure
        assert len(result) == len(scenario.expected_standings), (
            f"\n{'='*60}\n"
            f"SCENARIO: {scenario.id}\n"
            f"{'='*60}\n"
            f"Description: {scenario.description}\n"
            f"Business Rules: {scenario.business_rules_tested}\n"
            f"\nExpected {len(scenario.expected_standings)} teams in standings\n"
            f"Got {len(result)} teams\n"
            f"\nActual result: {result}\n"
            f"{'='*60}"
        )

        # Assert - verify each team's position and stats
        for expected in scenario.expected_standings:
            position = expected.position - 1  # 0-indexed

            if position < len(result):
                actual = result[position]

                # Verify team is in correct position
                assert actual["team"] == expected.team, (
                    f"\n{'='*60}\n"
                    f"SCENARIO: {scenario.id}\n"
                    f"{'='*60}\n"
                    f"Wrong team at position {expected.position}\n"
                    f"Expected: {expected.team}\n"
                    f"Got: {actual['team']}\n"
                    f"\nFull table:\n"
                    + "\n".join(f"  {i+1}. {t['team']} - {t['points']} pts"
                                for i, t in enumerate(result))
                    + f"\n{'='*60}"
                )

                # Verify all stats match
                stats_to_check = [
                    "played", "wins", "draws", "losses",
                    "goals_for", "goals_against", "goal_difference", "points"
                ]

                for stat in stats_to_check:
                    expected_value = getattr(expected, stat)
                    actual_value = actual[stat]
                    assert actual_value == expected_value, (
                        f"\n{'='*60}\n"
                        f"SCENARIO: {scenario.id}\n"
                        f"{'='*60}\n"
                        f"Team: {expected.team}\n"
                        f"Stat: {stat}\n"
                        f"Expected: {expected_value}\n"
                        f"Actual: {actual_value}\n"
                        f"\nBusiness Rules: {scenario.business_rules_tested}\n"
                        f"{'='*60}"
                    )


@pytest.mark.unit
@pytest.mark.standings
@allure.suite("Parameterized Tests")
@allure.sub_suite("League Table Scenarios")
@allure.feature("Test Quality")
@allure.story("Business Rule Coverage")
class TestBusinessRuleCoverage:
    """Meta-tests to verify business rule coverage."""

    @allure.severity(allure.severity_level.MINOR)
    def test_all_scenarios_have_business_rules(self):
        """Every scenario should document which rules it tests."""
        for scenario in LEAGUE_TABLE_SCENARIOS:
            assert len(scenario.business_rules_tested) > 0, (
                f"Scenario '{scenario.id}' must document business rules tested"
            )

    def test_core_business_rules_covered(self):
        """Verify core business rules are tested."""
        all_rules = []
        for scenario in LEAGUE_TABLE_SCENARIOS:
            all_rules.extend(scenario.business_rules_tested)

        all_rules_text = " ".join(all_rules).lower()

        # Core rules that must be tested
        core_rules = [
            "3 points for win",
            "1 point for draw",
            "goal difference",
            "completed",
        ]

        for rule in core_rules:
            assert rule.lower() in all_rules_text, (
                f"Core business rule not covered: {rule}\n"
                f"Covered rules: {all_rules}"
            )

    def test_scenario_coverage_summary(self):
        """Print scenario coverage summary."""
        print(f"\n{'='*60}")
        print("LEAGUE TABLE SCENARIO COVERAGE")
        print(f"{'='*60}")
        print(f"Total scenarios: {len(LEAGUE_TABLE_SCENARIOS)}")

        # Count business rules
        all_rules = []
        for scenario in LEAGUE_TABLE_SCENARIOS:
            all_rules.extend(scenario.business_rules_tested)

        unique_rules = set(all_rules)
        print(f"Unique business rules tested: {len(unique_rules)}")

        print("\nScenarios:")
        for s in LEAGUE_TABLE_SCENARIOS:
            print(f"  [{s.id}] {s.description}")
            for rule in s.business_rules_tested:
                print(f"    - {rule}")

        print(f"{'='*60}")

        # This test always passes - it's for documentation
        assert True


@pytest.mark.unit
@pytest.mark.standings
@allure.suite("Parameterized Tests")
@allure.sub_suite("League Table Scenarios")
@allure.feature("Business Logic")
@allure.story("Edge Cases")
class TestEdgeCases:
    """Additional edge case tests not covered by scenarios."""

    @allure.severity(allure.severity_level.NORMAL)
    def test_team_appears_in_multiple_matches(self):
        """Team stats accumulate correctly across multiple matches."""
        matches = [
            MatchData("Team A", "Team B", 2, 1),
            MatchData("Team A", "Team C", 1, 0),
            MatchData("Team B", "Team A", 0, 3),  # A plays as away team
        ]

        result = calculate_league_table(matches)

        # Find Team A
        team_a = next(t for t in result if t["team"] == "Team A")

        assert team_a["played"] == 3
        assert team_a["wins"] == 3
        assert team_a["goals_for"] == 6  # 2 + 1 + 3
        assert team_a["goals_against"] == 1  # 1 + 0 + 0
        assert team_a["points"] == 9

    def test_all_zeros_match(self):
        """0-0 draw is handled correctly."""
        matches = [MatchData("Team A", "Team B", 0, 0)]
        result = calculate_league_table(matches)

        assert len(result) == 2
        for team in result:
            assert team["points"] == 1
            assert team["draws"] == 1
            assert team["goals_for"] == 0
            assert team["goals_against"] == 0

    def test_cancelled_matches_excluded(self):
        """Cancelled matches don't count."""
        matches = [
            MatchData("Team A", "Team B", 2, 0, match_status="completed"),
            MatchData("Team A", "Team C", 5, 0, match_status="cancelled"),
        ]

        result = calculate_league_table(matches)

        team_a = next(t for t in result if t["team"] == "Team A")
        assert team_a["played"] == 1
        assert team_a["goals_for"] == 2  # Only from completed match


# ============================================================================
# Documentation Helper
# ============================================================================

def print_scenarios():
    """Print all scenarios for documentation."""
    print("\n" + "=" * 80)
    print("LEAGUE TABLE CALCULATION SCENARIOS")
    print("=" * 80)

    for s in LEAGUE_TABLE_SCENARIOS:
        print(f"\n[{s.id}] {s.description}")
        print(f"  Business Rules Tested:")
        for rule in s.business_rules_tested:
            print(f"    - {rule}")
        print(f"  Matches: {len(s.matches)}")
        print(f"  Expected Teams: {len(s.expected_standings)}")

        if s.expected_standings:
            print("  Expected Standings:")
            for standing in s.expected_standings:
                print(f"    {standing.position}. {standing.team}: "
                      f"{standing.points} pts, GD {standing.goal_difference:+d}")


if __name__ == "__main__":
    print_scenarios()
