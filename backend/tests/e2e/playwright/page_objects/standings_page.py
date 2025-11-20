"""
Standings Page Object for Missing Table league standings.

Handles:
- League table display
- Filtering by season, age group, division
- Sorting functionality
- Team details navigation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base_page import BasePage

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


@dataclass
class TeamStanding:
    """Data class representing a team's standing in the league table."""
    position: int
    team_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class StandingsPage(BasePage):
    """
    Page Object for the League Standings page.
    
    Usage:
        def test_standings_load(standings_page):
            standings_page.navigate()
            standings = standings_page.get_standings()
            assert len(standings) > 0
    """
    
    URL_PATH = "/"
    PAGE_TITLE = "Missing Table"
    LOAD_INDICATOR = "[data-testid='standings-table']"

    # Filters - using data-testid for stability
    AGE_GROUP_FILTER = "[data-testid='age-group-filter']"
    SEASON_FILTER = "[data-testid='season-filter']"
    DIVISION_FILTER = "[data-testid='division-filter']"

    # Table elements
    STANDINGS_TABLE = "[data-testid='standings-table']"
    TABLE_HEADER = "thead tr"
    TABLE_BODY = "[data-testid='standings-body']"
    TABLE_ROWS = "[data-testid='standings-row']"

    # Table columns (based on actual LeagueTable.vue structure)
    COL_POSITION = "td:nth-child(1)"
    COL_TEAM = "td:nth-child(2)"
    COL_PLAYED = "td:nth-child(3)"
    COL_WINS = "td:nth-child(4)"
    COL_DRAWS = "td:nth-child(5)"
    COL_LOSSES = "td:nth-child(6)"
    COL_GF = "td:nth-child(7)"
    COL_GA = "td:nth-child(8)"
    COL_GD = "td:nth-child(9)"
    COL_POINTS = "td:nth-child(10)"

    # Messages
    LOADING_MESSAGE = "[data-testid='loading-indicator']"
    ERROR_MESSAGE = "[data-testid='error-message']"
    NO_DATA_MESSAGE = "text=No standings, text=No data"

    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        super().__init__(page, base_url)

    # =========================================================================
    # Filter Actions
    # =========================================================================

    def select_season(self, season_name: str) -> StandingsPage:
        """Select a season from the filter dropdown."""
        logger.info(f"Selecting season: {season_name}")
        self.select_option(self.SEASON_FILTER, label=season_name)
        self.wait_for_table_update()
        return self

    def select_age_group(self, age_group: str) -> StandingsPage:
        """Select an age group from the filter dropdown."""
        logger.info(f"Selecting age group: {age_group}")
        self.select_option(self.AGE_GROUP_FILTER, label=age_group)
        self.wait_for_table_update()
        return self

    def select_division(self, division: str) -> StandingsPage:
        """Select a division from the filter dropdown."""
        logger.info(f"Selecting division: {division}")
        self.select_option(self.DIVISION_FILTER, label=division)
        self.wait_for_table_update()
        return self

    def select_match_type(self, match_type: str) -> StandingsPage:
        """Select a match type from the filter dropdown."""
        logger.info(f"Selecting match type: {match_type}")
        self.select_option(self.MATCH_TYPE_FILTER, label=match_type)
        self.wait_for_table_update()
        return self

    def apply_filters(
        self,
        season: str | None = None,
        age_group: str | None = None,
        division: str | None = None,
        match_type: str | None = None
    ) -> StandingsPage:
        """Apply multiple filters at once."""
        logger.info(f"Applying filters: season={season}, age_group={age_group}, division={division}")
        
        if season:
            self.select_season(season)
        if age_group:
            self.select_age_group(age_group)
        if division:
            self.select_division(division)
        if match_type:
            self.select_match_type(match_type)
        
        return self

    def wait_for_table_update(self) -> None:
        """Wait for table to update after filter change."""
        self.page.wait_for_timeout(500)  # Brief delay for API call
        self.wait_for_network_idle()

    # =========================================================================
    # Filter Queries
    # =========================================================================

    def get_selected_season(self) -> str:
        """Get currently selected season."""
        return self.get_value(self.SEASON_FILTER)

    def get_selected_age_group(self) -> str:
        """Get currently selected age group."""
        return self.get_value(self.AGE_GROUP_FILTER)

    def get_selected_division(self) -> str:
        """Get currently selected division."""
        return self.get_value(self.DIVISION_FILTER)

    def get_available_seasons(self) -> list[str]:
        """Get all available seasons in dropdown."""
        options = self.page.locator(f"{self.SEASON_FILTER} option")
        return [opt.inner_text() for opt in options.all()]

    def get_available_age_groups(self) -> list[str]:
        """Get all available age groups in dropdown."""
        options = self.page.locator(f"{self.AGE_GROUP_FILTER} option")
        return [opt.inner_text() for opt in options.all()]

    def get_available_divisions(self) -> list[str]:
        """Get all available divisions in dropdown."""
        options = self.page.locator(f"{self.DIVISION_FILTER} option")
        return [opt.inner_text() for opt in options.all()]

    # =========================================================================
    # Table Data Retrieval
    # =========================================================================

    def get_standings(self) -> list[TeamStanding]:
        """
        Get all team standings from the table.
        
        Returns:
            List of TeamStanding objects
        """
        logger.info("Getting standings data")
        standings = []
        
        rows = self.page.locator(self.TABLE_ROWS)
        count = rows.count()
        
        for i in range(count):
            row = rows.nth(i)
            try:
                standing = TeamStanding(
                    position=i + 1,
                    team_name=row.locator(self.COL_TEAM).inner_text().strip(),
                    played=self._parse_int(row.locator(self.COL_PLAYED).inner_text()),
                    wins=self._parse_int(row.locator(self.COL_WINS).inner_text()),
                    draws=self._parse_int(row.locator(self.COL_DRAWS).inner_text()),
                    losses=self._parse_int(row.locator(self.COL_LOSSES).inner_text()),
                    goals_for=self._parse_int(row.locator(self.COL_GF).inner_text()),
                    goals_against=self._parse_int(row.locator(self.COL_GA).inner_text()),
                    goal_difference=self._parse_int(row.locator(self.COL_GD).inner_text()),
                    points=self._parse_int(row.locator(self.COL_POINTS).inner_text()),
                )
                standings.append(standing)
            except Exception as e:
                logger.warning(f"Error parsing row {i}: {e}")
                continue
        
        return standings

    def get_team_count(self) -> int:
        """Get the number of teams in the standings."""
        return self.page.locator(self.TABLE_ROWS).count()

    def get_team_at_position(self, position: int) -> TeamStanding | None:
        """Get team at specific position (1-indexed)."""
        standings = self.get_standings()
        if 1 <= position <= len(standings):
            return standings[position - 1]
        return None

    def get_team_by_name(self, team_name: str) -> TeamStanding | None:
        """Get team standing by team name."""
        standings = self.get_standings()
        for standing in standings:
            if team_name.lower() in standing.team_name.lower():
                return standing
        return None

    def get_top_teams(self, count: int = 5) -> list[TeamStanding]:
        """Get top N teams from standings."""
        standings = self.get_standings()
        return standings[:count]

    def get_team_names(self) -> list[str]:
        """Get list of all team names in standings."""
        return self.get_all_texts(f"{self.TABLE_ROWS} {self.COL_TEAM}")

    # =========================================================================
    # Table Sorting
    # =========================================================================

    def click_column_header(self, column_name: str) -> StandingsPage:
        """Click on a column header to sort."""
        logger.info(f"Sorting by column: {column_name}")
        header = self.page.locator(f"{self.TABLE_HEADER} >> text={column_name}")
        header.click()
        self.wait_for_table_update()
        return self

    def sort_by_points(self) -> StandingsPage:
        """Sort table by points column."""
        return self.click_column_header("Pts")

    def sort_by_goal_difference(self) -> StandingsPage:
        """Sort table by goal difference column."""
        return self.click_column_header("GD")

    def sort_by_team_name(self) -> StandingsPage:
        """Sort table alphabetically by team name."""
        return self.click_column_header("Team")

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_table_visible(self) -> bool:
        """Check if standings table is visible."""
        return self.page.locator(self.STANDINGS_TABLE).is_visible()

    def has_standings_data(self) -> bool:
        """Check if table has any standings data."""
        return self.get_team_count() > 0

    def is_loading(self) -> bool:
        """Check if standings are loading."""
        return self.page.locator(self.LOADING_MESSAGE).is_visible()

    def has_error(self) -> bool:
        """Check if error message is displayed."""
        return self.page.locator(self.ERROR_MESSAGE).is_visible()

    def has_no_data_message(self) -> bool:
        """Check if no data message is displayed."""
        return self.page.locator(self.NO_DATA_MESSAGE).is_visible()

    # =========================================================================
    # Team Navigation
    # =========================================================================

    def click_team(self, team_name: str) -> None:
        """Click on a team name to view team details."""
        logger.info(f"Clicking on team: {team_name}")
        team_link = self.page.locator(f"{self.TABLE_ROWS} >> text={team_name}")
        team_link.click()
        self.page.wait_for_load_state("networkidle")

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    def validate_standings_sorted_by_points(self) -> bool:
        """Verify that standings are sorted by points in descending order."""
        standings = self.get_standings()
        if len(standings) < 2:
            return True
        
        for i in range(len(standings) - 1):
            if standings[i].points < standings[i + 1].points:
                return False
        return True

    def validate_point_calculations(self) -> bool:
        """Verify that points = wins * 3 + draws."""
        standings = self.get_standings()
        for standing in standings:
            expected_points = standing.wins * 3 + standing.draws
            if standing.points != expected_points:
                logger.error(
                    f"Invalid points for {standing.team_name}: "
                    f"got {standing.points}, expected {expected_points}"
                )
                return False
        return True

    def validate_games_played(self) -> bool:
        """Verify that played = wins + draws + losses."""
        standings = self.get_standings()
        for standing in standings:
            expected_played = standing.wins + standing.draws + standing.losses
            if standing.played != expected_played:
                logger.error(
                    f"Invalid games played for {standing.team_name}: "
                    f"got {standing.played}, expected {expected_played}"
                )
                return False
        return True

    def validate_goal_difference(self) -> bool:
        """Verify that GD = GF - GA."""
        standings = self.get_standings()
        for standing in standings:
            expected_gd = standing.goals_for - standing.goals_against
            if standing.goal_difference != expected_gd:
                logger.error(
                    f"Invalid GD for {standing.team_name}: "
                    f"got {standing.goal_difference}, expected {expected_gd}"
                )
                return False
        return True

    # =========================================================================
    # Utilities
    # =========================================================================

    @staticmethod
    def _parse_int(text: str) -> int:
        """Parse integer from text, handling edge cases."""
        text = text.strip()
        if not text or text == "-":
            return 0
        # Handle goal difference with +/- prefix
        return int(text.replace("+", ""))
