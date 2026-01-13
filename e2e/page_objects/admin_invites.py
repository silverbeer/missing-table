"""
Admin Invites Section Page Object for Missing Table admin panel.

Handles:
- Invite creation
- Invite listing
- Invite cancellation
- Invite filtering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .base_page import Component

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

logger = logging.getLogger(__name__)


class InviteType(Enum):
    """Invite types available in the system."""
    CLUB_MANAGER = "club_manager"
    CLUB_FAN = "club_fan"
    TEAM_MANAGER = "team_manager"
    TEAM_PLAYER = "team_player"


class InviteStatus(Enum):
    """Invite status values."""
    ALL = ""
    PENDING = "pending"
    USED = "used"
    EXPIRED = "expired"


@dataclass
class InviteRow:
    """Data class representing an invite row in the admin table."""
    id: str | None
    code: str
    invite_type: str
    club_or_team: str
    status: str
    created_at: str


class AdminInvitesSection(Component):
    """
    Page Object for the Admin Invites section.

    This component handles invite management within the admin panel.

    Usage:
        def test_create_invite(admin_page):
            admin_page.navigate()
            admin_page.go_to_invites()

            invites = AdminInvitesSection(admin_page.page)
            invites.create_team_invite(
                team="Test FC",
                age_group="U14",
                invite_type=InviteType.TEAM_PLAYER
            )
            assert invites.is_success_message_visible()
    """

    ROOT = "[data-testid='admin-invites']"
    LOAD_INDICATOR = "[data-testid='admin-invites']"

    # Main sections
    CONTAINER = "[data-testid='admin-invites']"
    CREATE_SECTION = "[data-testid='create-invite-section']"
    EXISTING_SECTION = "[data-testid='existing-invites-section']"

    # Create invite form
    CREATE_FORM = "[data-testid='create-invite-form']"
    INVITE_TYPE_SELECT = "[data-testid='invite-type-select']"
    CLUB_SELECT = "[data-testid='invite-club-select']"
    TEAM_SELECT = "[data-testid='invite-team-select']"
    AGE_GROUP_SELECT = "[data-testid='invite-age-group-select']"
    EMAIL_INPUT = "[data-testid='invite-email-input']"
    CREATE_SUBMIT = "[data-testid='create-invite-submit']"

    # Success message
    SUCCESS_MESSAGE = "[data-testid='invite-success-message']"
    COPY_MESSAGE_BUTTON = "[data-testid='copy-invite-message-button']"
    COPY_LINK_BUTTON = "[data-testid='copy-invite-link-button']"

    # Existing invites table
    STATUS_FILTER = "[data-testid='invite-status-filter']"
    TABLE_CONTAINER = "[data-testid='invites-table-container']"
    TABLE = "[data-testid='invites-table']"
    TABLE_BODY = "[data-testid='invites-tbody']"
    INVITE_ROW = "[data-invite-row]"
    INVITE_CODE = "[data-testid='invite-code']"
    CANCEL_BUTTON = "[data-testid='cancel-invite-button']"

    def __init__(self, page: Page) -> None:
        super().__init__(page, self.ROOT)

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_loaded(self) -> bool:
        """Check if invites section is loaded."""
        return self.is_visible(self.CONTAINER)

    def is_success_message_visible(self) -> bool:
        """Check if the success message is visible."""
        return self.is_visible(self.SUCCESS_MESSAGE)

    def is_form_visible(self) -> bool:
        """Check if the create form is visible."""
        return self.is_visible(self.CREATE_FORM)

    def get_success_message_text(self) -> str:
        """Get the success message text."""
        if self.is_success_message_visible():
            return self.get_text(self.SUCCESS_MESSAGE)
        return ""

    # =========================================================================
    # Form Field Visibility
    # =========================================================================

    def is_club_select_visible(self) -> bool:
        """Check if club select is visible (for club-level invites)."""
        return self.is_visible(self.CLUB_SELECT)

    def is_team_select_visible(self) -> bool:
        """Check if team select is visible (for team-level invites)."""
        return self.is_visible(self.TEAM_SELECT)

    def is_age_group_select_visible(self) -> bool:
        """Check if age group select is visible (for team-level invites)."""
        return self.is_visible(self.AGE_GROUP_SELECT)

    # =========================================================================
    # Create Invite Operations
    # =========================================================================

    def select_invite_type(self, invite_type: InviteType) -> None:
        """Select the invite type."""
        logger.info(f"Selecting invite type: {invite_type.value}")
        self.select_option(self.INVITE_TYPE_SELECT, value=invite_type.value)
        # Wait for dependent fields to appear
        self.page.wait_for_timeout(300)

    def select_club(self, club_name: str) -> None:
        """Select a club from the dropdown."""
        logger.info(f"Selecting club: {club_name}")
        self.select_option(self.CLUB_SELECT, label=club_name)

    def select_team(self, team_name: str) -> None:
        """Select a team from the dropdown."""
        logger.info(f"Selecting team: {team_name}")
        self.select_option(self.TEAM_SELECT, label=team_name)

    def select_age_group(self, age_group: str) -> None:
        """Select an age group from the dropdown."""
        logger.info(f"Selecting age group: {age_group}")
        self.select_option(self.AGE_GROUP_SELECT, label=age_group)

    def fill_email(self, email: str) -> None:
        """Fill in the optional email field."""
        self.fill(self.EMAIL_INPUT, email)

    def click_create(self) -> None:
        """Click the create invite button."""
        self.click(self.CREATE_SUBMIT)
        # Wait for response
        self.page.wait_for_timeout(500)
        self.wait_for_network_idle()

    def create_club_invite(
        self,
        club: str,
        invite_type: InviteType = InviteType.CLUB_FAN,
        email: str | None = None,
    ) -> None:
        """Create a club-level invite (club_manager or club_fan)."""
        logger.info(f"Creating {invite_type.value} invite for club: {club}")

        self.select_invite_type(invite_type)
        self.select_club(club)

        if email:
            self.fill_email(email)

        self.click_create()

    def create_team_invite(
        self,
        team: str,
        age_group: str,
        invite_type: InviteType = InviteType.TEAM_PLAYER,
        email: str | None = None,
    ) -> None:
        """Create a team-level invite (team_manager or team_player)."""
        logger.info(f"Creating {invite_type.value} invite for team: {team}")

        self.select_invite_type(invite_type)
        self.select_team(team)
        self.select_age_group(age_group)

        if email:
            self.fill_email(email)

        self.click_create()

    def copy_invite_message(self) -> None:
        """Click the copy invite message button."""
        self.click(self.COPY_MESSAGE_BUTTON)

    def copy_invite_link(self) -> None:
        """Click the copy invite link button."""
        self.click(self.COPY_LINK_BUTTON)

    # =========================================================================
    # Invite List Operations
    # =========================================================================

    def filter_by_status(self, status: InviteStatus) -> None:
        """Filter invites by status."""
        logger.info(f"Filtering invites by status: {status.value}")
        self.select_option(self.STATUS_FILTER, value=status.value)
        self.wait_for_network_idle()

    def get_invite_count(self) -> int:
        """Get the number of invites in the table."""
        return self.page.locator(self.INVITE_ROW).count()

    def get_invite_rows(self) -> list[InviteRow]:
        """Get all invite rows from the table."""
        rows = []
        row_locators = self.page.locator(self.INVITE_ROW)
        count = row_locators.count()

        for i in range(count):
            row = row_locators.nth(i)
            invite_id = row.get_attribute("data-testid")
            if invite_id:
                invite_id = invite_id.replace("invite-row-", "")

            rows.append(InviteRow(
                id=invite_id,
                code=self._get_text_or_empty(row, self.INVITE_CODE),
                invite_type=self._get_cell_text(row, 1),
                club_or_team=self._get_cell_text(row, 2),
                status=self._get_cell_text(row, 3),
                created_at=self._get_cell_text(row, 4),
            ))

        return rows

    def get_invite_codes(self) -> list[str]:
        """Get list of all invite codes."""
        invites = self.get_invite_rows()
        return [inv.code for inv in invites]

    def find_invite_row(self, code: str) -> Locator | None:
        """Find an invite row by code."""
        rows = self.page.locator(self.INVITE_ROW)
        count = rows.count()

        for i in range(count):
            row = rows.nth(i)
            row_code = self._get_text_or_empty(row, self.INVITE_CODE)
            if code in row_code:
                return row

        return None

    def cancel_invite(self, code: str) -> None:
        """Cancel an invite by its code."""
        logger.info(f"Cancelling invite: {code}")
        row = self.find_invite_row(code)
        if row is None:
            raise ValueError(f"Invite not found: {code}")

        cancel_button = row.locator(self.CANCEL_BUTTON)
        if cancel_button.count() > 0:
            cancel_button.click()
            # Handle confirmation dialog
            self.page.wait_for_timeout(300)
            self.wait_for_network_idle()
        else:
            raise ValueError(f"Invite {code} cannot be cancelled (not pending)")

    def get_pending_invites(self) -> list[InviteRow]:
        """Get only pending invites."""
        invites = self.get_invite_rows()
        return [inv for inv in invites if inv.status.lower() == "pending"]

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
