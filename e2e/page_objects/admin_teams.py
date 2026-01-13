"""
Admin Teams Section Page Object for Missing Table admin panel.

Handles:
- Teams list viewing
- Team creation
- Team editing
- Team deletion
- Team league mappings
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .base_page import Component

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

logger = logging.getLogger(__name__)


@dataclass
class TeamRow:
    """Data class representing a team row in the admin table."""
    id: str | None
    name: str
    parent_club: str | None
    league: str | None
    age_groups: list[str]


class AdminTeamsSection(Component):
    """
    Page Object for the Admin Teams section.

    This component handles team management within the admin panel.

    Usage:
        def test_create_team(admin_page):
            admin_page.navigate()
            admin_page.go_to_teams()

            teams = AdminTeamsSection(admin_page.page)
            teams.click_add_team()
            teams.fill_team_form(
                name="Test FC",
                city="Test City",
                league="Academy",
                division="Northeast",
                team_type="league",
                age_groups=["U14", "U15"]
            )
            teams.submit_team_form()
    """

    ROOT = "[data-testid='admin-teams']"
    LOAD_INDICATOR = "[data-testid='teams-table']"

    # Container elements
    CONTAINER = "[data-testid='admin-teams']"
    ADD_TEAM_BUTTON = "[data-testid='add-team-button']"

    # Loading and error states
    LOADING = "[data-testid='teams-loading']"
    ERROR = "[data-testid='teams-error']"

    # Table elements
    TABLE_CONTAINER = "[data-testid='teams-table-container']"
    TABLE = "[data-testid='teams-table']"
    TABLE_BODY = "[data-testid='teams-tbody']"
    TEAM_ROW = "[data-team-row]"
    TEAM_NAME = "[data-testid='team-name']"

    # Row action buttons
    EDIT_BUTTON = "[data-testid='edit-team-button']"
    MANAGE_LEAGUES_BUTTON = "[data-testid='manage-leagues-button']"
    DELETE_BUTTON = "[data-testid='delete-team-button']"

    # Modal elements
    MODAL_OVERLAY = "[data-testid='team-modal-overlay']"
    MODAL = "[data-testid='team-modal']"
    MODAL_TITLE = "[data-testid='team-modal-title']"
    MODAL_FORM = "[data-testid='team-form']"
    MODAL_CANCEL = "[data-testid='team-modal-cancel']"
    MODAL_SUBMIT = "[data-testid='team-modal-submit']"

    # Form fields
    NAME_INPUT = "[data-testid='team-name-input']"
    CITY_INPUT = "[data-testid='team-city-input']"
    CLUB_SELECT = "[data-testid='team-club-select']"
    LEAGUE_SELECT = "[data-testid='team-league-select']"
    DIVISION_SELECT = "[data-testid='team-division-select']"
    TEAM_TYPE_SELECT = "[data-testid='team-type-select']"

    def __init__(self, page: Page) -> None:
        super().__init__(page, self.ROOT)

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_loaded(self) -> bool:
        """Check if teams section is loaded."""
        return self.is_visible(self.TABLE)

    def is_loading(self) -> bool:
        """Check if teams are loading."""
        return self.is_visible(self.LOADING)

    def has_error(self) -> bool:
        """Check if there's an error message."""
        return self.is_visible(self.ERROR)

    def get_error_message(self) -> str:
        """Get the error message text."""
        if self.has_error():
            return self.get_text(self.ERROR)
        return ""

    def is_modal_open(self) -> bool:
        """Check if the team modal is open."""
        return self.is_visible(self.MODAL)

    def get_modal_title(self) -> str:
        """Get the modal title text."""
        if self.is_modal_open():
            return self.get_text(self.MODAL_TITLE)
        return ""

    def wait_for_teams_loaded(self) -> None:
        """Wait for teams table to be visible."""
        self.page.wait_for_selector(self.TABLE, state="visible", timeout=10000)
        self.wait_for_network_idle()

    # =========================================================================
    # Team List Operations
    # =========================================================================

    def get_team_count(self) -> int:
        """Get the number of teams in the table."""
        return self.page.locator(self.TEAM_ROW).count()

    def get_team_rows(self) -> list[TeamRow]:
        """Get all team rows from the table."""
        rows = []
        row_locators = self.page.locator(self.TEAM_ROW)
        count = row_locators.count()

        for i in range(count):
            row = row_locators.nth(i)
            team_id = row.get_attribute("data-testid")
            if team_id:
                team_id = team_id.replace("team-row-", "")

            rows.append(TeamRow(
                id=team_id,
                name=self._get_text_or_empty(row, self.TEAM_NAME),
                parent_club=self._get_cell_text(row, 1),  # Second column
                league=self._get_cell_text(row, 2),  # Third column
                age_groups=self._get_age_groups(row),
            ))

        return rows

    def get_team_names(self) -> list[str]:
        """Get list of all team names."""
        teams = self.get_team_rows()
        return [t.name for t in teams]

    def find_team_row(self, team_name: str) -> Locator | None:
        """Find a team row by name."""
        rows = self.page.locator(self.TEAM_ROW)
        count = rows.count()

        for i in range(count):
            row = rows.nth(i)
            name = self._get_text_or_empty(row, self.TEAM_NAME)
            if team_name.lower() in name.lower():
                return row

        return None

    def team_exists(self, team_name: str) -> bool:
        """Check if a team with the given name exists."""
        return self.find_team_row(team_name) is not None

    # =========================================================================
    # Team CRUD Operations
    # =========================================================================

    def click_add_team(self) -> None:
        """Click the Add Team button to open the creation modal."""
        logger.info("Clicking Add Team button")
        self.click(self.ADD_TEAM_BUTTON)
        self.wait_for_modal()

    def click_edit_team(self, team_name: str) -> None:
        """Click the Edit button for a specific team."""
        logger.info(f"Clicking Edit for team: {team_name}")
        row = self.find_team_row(team_name)
        if row is None:
            raise ValueError(f"Team not found: {team_name}")
        row.locator(self.EDIT_BUTTON).click()
        self.wait_for_modal()

    def click_manage_leagues(self, team_name: str) -> None:
        """Click the Leagues button for a specific team."""
        logger.info(f"Clicking Leagues for team: {team_name}")
        row = self.find_team_row(team_name)
        if row is None:
            raise ValueError(f"Team not found: {team_name}")
        row.locator(self.MANAGE_LEAGUES_BUTTON).click()
        # Wait for mappings modal
        self.page.wait_for_timeout(500)
        self.wait_for_network_idle()

    def click_delete_team(self, team_name: str) -> None:
        """Click the Delete button for a specific team."""
        logger.info(f"Clicking Delete for team: {team_name}")
        row = self.find_team_row(team_name)
        if row is None:
            raise ValueError(f"Team not found: {team_name}")
        row.locator(self.DELETE_BUTTON).click()

    def confirm_delete(self) -> None:
        """Accept the browser confirmation dialog."""
        self.page.on("dialog", lambda dialog: dialog.accept())

    def cancel_delete(self) -> None:
        """Dismiss the browser confirmation dialog."""
        self.page.on("dialog", lambda dialog: dialog.dismiss())

    # =========================================================================
    # Modal Operations
    # =========================================================================

    def wait_for_modal(self) -> None:
        """Wait for the team modal to be visible."""
        self.page.wait_for_selector(self.MODAL, state="visible", timeout=5000)

    def close_modal(self) -> None:
        """Close the modal by clicking Cancel."""
        self.click(self.MODAL_CANCEL)
        self.page.wait_for_selector(self.MODAL, state="hidden", timeout=5000)

    def submit_modal(self) -> None:
        """Submit the modal form."""
        self.click(self.MODAL_SUBMIT)
        # Wait for modal to close or error to appear
        self.page.wait_for_timeout(500)
        self.wait_for_network_idle()

    def fill_team_form(
        self,
        name: str,
        city: str | None = None,
        club: str | None = None,
        league: str | None = None,
        division: str | None = None,
        team_type: str | None = None,
        age_groups: list[str] | None = None,
    ) -> None:
        """Fill in the team creation/edit form."""
        logger.info(f"Filling team form: {name}")

        # Fill required fields
        self.fill(self.NAME_INPUT, name)

        if city:
            self.fill(self.CITY_INPUT, city)

        if club:
            self.select_option(self.CLUB_SELECT, label=club)

        if league and self.is_visible(self.LEAGUE_SELECT):
            self.select_option(self.LEAGUE_SELECT, label=league)

        if division and self.is_visible(self.DIVISION_SELECT):
            self.select_option(self.DIVISION_SELECT, label=division)

        if team_type and self.is_visible(self.TEAM_TYPE_SELECT):
            self.select_option(self.TEAM_TYPE_SELECT, value=team_type)

        # Age groups are checkboxes - would need more specific handling
        if age_groups:
            for age_group in age_groups:
                checkbox_label = self.page.locator(f"label:has-text('{age_group}')")
                if checkbox_label.count() > 0:
                    checkbox = checkbox_label.locator("input[type='checkbox']")
                    if not checkbox.is_checked():
                        checkbox.check()

    def create_team(
        self,
        name: str,
        city: str | None = None,
        club: str | None = None,
        league: str | None = None,
        division: str | None = None,
        team_type: str = "league",
        age_groups: list[str] | None = None,
    ) -> None:
        """Complete workflow to create a new team."""
        self.click_add_team()
        self.fill_team_form(
            name=name,
            city=city,
            club=club,
            league=league,
            division=division,
            team_type=team_type,
            age_groups=age_groups,
        )
        self.submit_modal()

    # =========================================================================
    # Utilities
    # =========================================================================

    def _get_text_or_empty(self, parent: Locator, selector: str) -> str:
        """Get text from element or empty string if not found."""
        element = parent.locator(selector)
        if element.count() > 0:
            return element.inner_text().strip()
        return ""

    def _get_cell_text(self, row: Locator, index: int) -> str:
        """Get text from a table cell by index."""
        cell = row.locator("td").nth(index)
        if cell.count() > 0:
            return cell.inner_text().strip()
        return ""

    def _get_age_groups(self, row: Locator) -> list[str]:
        """Extract age group badges from a row."""
        age_groups = []
        # Age groups are in the 4th column (index 3)
        cell = row.locator("td").nth(3)
        badges = cell.locator("span")
        count = badges.count()
        for i in range(count):
            text = badges.nth(i).inner_text().strip()
            if text:
                age_groups.append(text)
        return age_groups
