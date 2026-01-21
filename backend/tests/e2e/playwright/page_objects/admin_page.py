"""
Admin Page Object for Missing Table admin panel.

Handles:
- Admin dashboard
- Team management
- Match management
- User management
- Invite management
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base_page import BasePage

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class AdminPage(BasePage):
    """
    Page Object for the Admin Panel.

    This page requires admin authentication.

    Usage:
        def test_admin_access(admin_page, authenticated_admin):
            admin_page.navigate()
            assert admin_page.is_dashboard_visible()
    """

    URL_PATH = "/admin"
    PAGE_TITLE = "Admin"
    LOAD_INDICATOR = ".admin-dashboard, [data-testid='admin-panel']"

    # Navigation tabs
    TAB_DASHBOARD = "text=Dashboard, [data-testid='tab-dashboard']"
    TAB_TEAMS = "text=Teams, [data-testid='tab-teams']"
    TAB_MATCHES = "text=Matches, [data-testid='tab-matches']"
    TAB_USERS = "text=Users, [data-testid='tab-users']"
    TAB_INVITES = "text=Invites, [data-testid='tab-invites']"
    TAB_SETTINGS = "text=Settings, [data-testid='tab-settings']"

    # Dashboard elements
    DASHBOARD = ".admin-dashboard, [data-testid='admin-dashboard']"
    STATS_CARDS = ".stats-card, [data-testid='stats-card']"

    # Team management
    TEAMS_LIST = ".teams-list, [data-testid='teams-list']"
    ADD_TEAM_BUTTON = "button:has-text('Add Team'), [data-testid='add-team']"
    TEAM_ROWS = ".team-row, [data-testid='team-row']"

    # Match management
    MATCHES_LIST = ".matches-list, [data-testid='matches-list']"
    ADD_MATCH_BUTTON = "button:has-text('Add Match'), [data-testid='add-match']"
    MATCH_ROWS = ".match-row, [data-testid='match-row']"

    # User management
    USERS_LIST = ".users-list, [data-testid='users-list']"
    USER_ROWS = ".user-row, [data-testid='user-row']"

    # Invite management
    INVITES_LIST = ".invites-list, [data-testid='invites-list']"
    CREATE_INVITE_BUTTON = "button:has-text('Create Invite'), [data-testid='create-invite']"
    INVITE_ROWS = ".invite-row, [data-testid='invite-row']"

    # Modal/Dialog
    MODAL = ".modal, [role='dialog'], [data-testid='modal']"
    MODAL_CLOSE = ".modal-close, [data-testid='modal-close'], button:has-text('Close')"
    MODAL_SUBMIT = ".modal-submit, [data-testid='modal-submit'], button[type='submit']"
    MODAL_CANCEL = ".modal-cancel, [data-testid='modal-cancel'], button:has-text('Cancel')"

    # Messages
    SUCCESS_MESSAGE = ".success, [data-testid='success-message'], .text-green-500"
    ERROR_MESSAGE = ".error, [data-testid='error-message'], .text-red-500"
    ACCESS_DENIED = "text=Access Denied, text=Unauthorized, text=Not Authorized"

    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        super().__init__(page, base_url)

    # =========================================================================
    # Navigation
    # =========================================================================

    def go_to_dashboard(self) -> AdminPage:
        """Navigate to dashboard tab."""
        self.click(self.TAB_DASHBOARD)
        self.wait_for_network_idle()
        return self

    def go_to_teams(self) -> AdminPage:
        """Navigate to teams management tab."""
        self.click(self.TAB_TEAMS)
        self.wait_for_network_idle()
        return self

    def go_to_matches(self) -> AdminPage:
        """Navigate to matches management tab."""
        self.click(self.TAB_MATCHES)
        self.wait_for_network_idle()
        return self

    def go_to_users(self) -> AdminPage:
        """Navigate to users management tab."""
        self.click(self.TAB_USERS)
        self.wait_for_network_idle()
        return self

    def go_to_invites(self) -> AdminPage:
        """Navigate to invites management tab."""
        self.click(self.TAB_INVITES)
        self.wait_for_network_idle()
        return self

    def go_to_settings(self) -> AdminPage:
        """Navigate to settings tab."""
        self.click(self.TAB_SETTINGS)
        self.wait_for_network_idle()
        return self

    # =========================================================================
    # Dashboard
    # =========================================================================

    def is_dashboard_visible(self) -> bool:
        """Check if admin dashboard is visible."""
        return self.is_visible(self.DASHBOARD)

    def get_stats_count(self) -> int:
        """Get number of stats cards on dashboard."""
        return self.count_elements(self.STATS_CARDS)

    def get_stat_value(self, stat_name: str) -> str:
        """Get value of a specific stat by name."""
        card = self.page.locator(f"{self.STATS_CARDS}:has-text('{stat_name}')")
        value_elem = card.locator(".stat-value, .value, h2, .text-2xl")
        if value_elem.count() > 0:
            return value_elem.inner_text()
        return ""

    # =========================================================================
    # Team Management
    # =========================================================================

    def click_add_team(self) -> AdminPage:
        """Click add team button."""
        self.click(self.ADD_TEAM_BUTTON)
        self.wait_for_modal()
        return self

    def get_team_count(self) -> int:
        """Get number of teams in list."""
        return self.count_elements(self.TEAM_ROWS)

    def get_team_names(self) -> list[str]:
        """Get list of team names."""
        return self.get_all_texts(f"{self.TEAM_ROWS} .team-name")

    def click_edit_team(self, team_name: str) -> AdminPage:
        """Click edit button for a specific team."""
        row = self.page.locator(f"{self.TEAM_ROWS}:has-text('{team_name}')")
        row.locator("button:has-text('Edit'), [data-testid='edit-team']").click()
        self.wait_for_modal()
        return self

    def click_delete_team(self, team_name: str) -> AdminPage:
        """Click delete button for a specific team."""
        row = self.page.locator(f"{self.TEAM_ROWS}:has-text('{team_name}')")
        row.locator("button:has-text('Delete'), [data-testid='delete-team']").click()
        return self

    # =========================================================================
    # Match Management
    # =========================================================================

    def click_add_match(self) -> AdminPage:
        """Click add match button."""
        self.click(self.ADD_MATCH_BUTTON)
        self.wait_for_modal()
        return self

    def get_match_count(self) -> int:
        """Get number of matches in list."""
        return self.count_elements(self.MATCH_ROWS)

    def click_edit_match(self, index: int) -> AdminPage:
        """Click edit button for match at index."""
        row = self.page.locator(self.MATCH_ROWS).nth(index)
        row.locator("button:has-text('Edit'), [data-testid='edit-match']").click()
        self.wait_for_modal()
        return self

    # =========================================================================
    # User Management
    # =========================================================================

    def get_user_count(self) -> int:
        """Get number of users in list."""
        return self.count_elements(self.USER_ROWS)

    def search_user(self, query: str) -> AdminPage:
        """Search for a user."""
        search_input = self.page.locator("input[placeholder*='Search'], #user-search")
        search_input.fill(query)
        search_input.press("Enter")
        self.wait_for_network_idle()
        return self

    def change_user_role(self, email: str, new_role: str) -> AdminPage:
        """Change a user's role."""
        row = self.page.locator(f"{self.USER_ROWS}:has-text('{email}')")
        role_select = row.locator("select, [data-testid='role-select']")
        role_select.select_option(label=new_role)
        self.wait_for_network_idle()
        return self

    # =========================================================================
    # Invite Management
    # =========================================================================

    def click_create_invite(self) -> AdminPage:
        """Click create invite button."""
        self.click(self.CREATE_INVITE_BUTTON)
        self.wait_for_modal()
        return self

    def get_invite_count(self) -> int:
        """Get number of invites in list."""
        return self.count_elements(self.INVITE_ROWS)

    def get_invite_codes(self) -> list[str]:
        """Get list of invite codes."""
        return self.get_all_texts(f"{self.INVITE_ROWS} .invite-code")

    def copy_invite_code(self, index: int = 0) -> str:
        """Copy invite code at index."""
        row = self.page.locator(self.INVITE_ROWS).nth(index)
        copy_btn = row.locator("button:has-text('Copy'), [data-testid='copy-invite']")
        copy_btn.click()
        # Get code from the row
        code = row.locator(".invite-code").inner_text()
        return code

    def cancel_invite(self, code: str) -> AdminPage:
        """Cancel a specific invite."""
        row = self.page.locator(f"{self.INVITE_ROWS}:has-text('{code}')")
        cancel_btn = row.locator("button:has-text('Cancel'), [data-testid='cancel-invite']")
        cancel_btn.click()
        self.wait_for_network_idle()
        return self

    # =========================================================================
    # Modal Actions
    # =========================================================================

    def wait_for_modal(self) -> None:
        """Wait for modal to appear."""
        self.page.wait_for_selector(self.MODAL, state="visible", timeout=5000)

    def is_modal_visible(self) -> bool:
        """Check if modal is visible."""
        return self.is_visible(self.MODAL)

    def close_modal(self) -> AdminPage:
        """Close the modal dialog."""
        self.click(self.MODAL_CLOSE)
        self.page.wait_for_selector(self.MODAL, state="hidden")
        return self

    def submit_modal(self) -> AdminPage:
        """Submit the modal form."""
        self.click(self.MODAL_SUBMIT)
        self.wait_for_network_idle()
        return self

    def cancel_modal(self) -> AdminPage:
        """Cancel and close modal."""
        self.click(self.MODAL_CANCEL)
        self.page.wait_for_selector(self.MODAL, state="hidden")
        return self

    def fill_modal_field(self, field_name: str, value: str) -> AdminPage:
        """Fill a field in the modal by label or name."""
        modal = self.page.locator(self.MODAL)
        field = modal.locator(f"input[name='{field_name}'], label:has-text('{field_name}') + input")
        field.fill(value)
        return self

    def select_modal_option(self, field_name: str, value: str) -> AdminPage:
        """Select an option in modal by label."""
        modal = self.page.locator(self.MODAL)
        select = modal.locator(f"select[name='{field_name}'], label:has-text('{field_name}') + select")
        select.select_option(label=value)
        return self

    # =========================================================================
    # State Queries
    # =========================================================================

    def has_access(self) -> bool:
        """Check if user has access to admin panel."""
        return not self.is_visible(self.ACCESS_DENIED)

    def has_success_message(self) -> bool:
        """Check if success message is displayed."""
        return self.is_visible(self.SUCCESS_MESSAGE)

    def get_success_message(self) -> str:
        """Get success message text."""
        if self.has_success_message():
            return self.get_text(self.SUCCESS_MESSAGE)
        return ""

    def has_error_message(self) -> bool:
        """Check if error message is displayed."""
        return self.is_visible(self.ERROR_MESSAGE)

    def get_error_message(self) -> str:
        """Get error message text."""
        if self.has_error_message():
            return self.get_text(self.ERROR_MESSAGE)
        return ""

    def is_loading(self) -> bool:
        """Check if admin panel is loading."""
        return self.is_visible(".loading, .spinner")

    # =========================================================================
    # Convenience Methods for Common Workflows
    # =========================================================================

    def create_team(
        self,
        name: str,
        age_group: str,
        division: str | None = None,
        coach: str | None = None,
        email: str | None = None,
    ) -> AdminPage:
        """Complete workflow to create a new team."""
        logger.info(f"Creating team: {name}")
        self.go_to_teams()
        self.click_add_team()
        self.fill_modal_field("name", name)
        self.select_modal_option("age_group", age_group)
        if division:
            self.select_modal_option("division", division)
        if coach:
            self.fill_modal_field("coach", coach)
        if email:
            self.fill_modal_field("email", email)
        self.submit_modal()
        return self

    def create_invite(self, email: str, invite_type: str = "team_manager", team: str | None = None) -> str:
        """Complete workflow to create a new invite and return the code."""
        logger.info(f"Creating {invite_type} invite for: {email}")
        self.go_to_invites()
        self.click_create_invite()
        self.fill_modal_field("email", email)
        self.select_modal_option("type", invite_type)
        if team:
            self.select_modal_option("team", team)
        self.submit_modal()

        # Wait for invite to appear and get code
        self.page.wait_for_timeout(1000)
        codes = self.get_invite_codes()
        return codes[0] if codes else ""
