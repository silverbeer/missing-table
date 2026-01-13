"""
Admin Page Object for Missing Table admin panel.

Handles:
- Admin panel navigation
- Section switching
- Access control verification
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from .base_page import BasePage

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class AdminSection(Enum):
    """Admin panel sections with their navigation IDs."""
    INVITE_REQUESTS = "invite-requests"
    AGE_GROUPS = "age-groups"
    SEASONS = "seasons"
    LEAGUES = "leagues"
    DIVISIONS = "divisions"
    CLUBS = "clubs"
    TEAMS = "teams"
    PLAYERS = "players"
    MATCHES = "matches"
    INVITES = "invites"


class AdminPage(BasePage):
    """
    Page Object for the Admin Panel.

    This page requires admin or club_manager authentication.

    Usage:
        def test_admin_access(admin_page, authenticated_admin):
            admin_page.navigate()
            assert admin_page.is_loaded()
            admin_page.go_to_section(AdminSection.TEAMS)
    """

    URL_PATH = "/admin"
    PAGE_TITLE = None  # Don't verify title - might redirect to login
    LOAD_INDICATOR = None  # Don't wait for admin panel - might redirect

    # Main panel elements
    ADMIN_PANEL = "[data-testid='admin-panel']"
    ACCESS_DENIED = "[data-testid='admin-access-denied']"
    ADMIN_NAV = "[data-testid='admin-nav']"
    ADMIN_CONTENT = "[data-testid='admin-content']"

    # Section content containers
    SECTION_INVITE_REQUESTS = "[data-testid='admin-section-invite-requests']"
    SECTION_AGE_GROUPS = "[data-testid='admin-section-age-groups']"
    SECTION_SEASONS = "[data-testid='admin-section-seasons']"
    SECTION_LEAGUES = "[data-testid='admin-section-leagues']"
    SECTION_DIVISIONS = "[data-testid='admin-section-divisions']"
    SECTION_CLUBS = "[data-testid='admin-section-clubs']"
    SECTION_TEAMS = "[data-testid='admin-section-teams']"
    SECTION_PLAYERS = "[data-testid='admin-section-players']"
    SECTION_MATCHES = "[data-testid='admin-section-matches']"
    SECTION_INVITES = "[data-testid='admin-section-invites']"

    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        super().__init__(page, base_url)

    # =========================================================================
    # Navigation
    # =========================================================================

    def get_tab_selector(self, section: AdminSection) -> str:
        """Get the selector for a section tab button."""
        return f"[data-testid='admin-tab-{section.value}']"

    def get_section_selector(self, section: AdminSection) -> str:
        """Get the selector for a section content container."""
        return f"[data-testid='admin-section-{section.value}']"

    def go_to_section(self, section: AdminSection) -> AdminPage:
        """Navigate to a specific admin section."""
        logger.info(f"Navigating to admin section: {section.value}")
        tab_selector = self.get_tab_selector(section)
        self.click(tab_selector)
        self.wait_for_section(section)
        return self

    def wait_for_section(self, section: AdminSection) -> None:
        """Wait for a section to be visible."""
        section_selector = self.get_section_selector(section)
        self.page.wait_for_selector(section_selector, state="visible", timeout=5000)
        self.wait_for_network_idle()

    def go_to_teams(self) -> AdminPage:
        """Navigate to teams section."""
        return self.go_to_section(AdminSection.TEAMS)

    def go_to_invites(self) -> AdminPage:
        """Navigate to invites section."""
        return self.go_to_section(AdminSection.INVITES)

    def go_to_matches(self) -> AdminPage:
        """Navigate to matches section."""
        return self.go_to_section(AdminSection.MATCHES)

    def go_to_players(self) -> AdminPage:
        """Navigate to players section."""
        return self.go_to_section(AdminSection.PLAYERS)

    def go_to_clubs(self) -> AdminPage:
        """Navigate to clubs section (admin only)."""
        return self.go_to_section(AdminSection.CLUBS)

    def go_to_seasons(self) -> AdminPage:
        """Navigate to seasons section (admin only)."""
        return self.go_to_section(AdminSection.SEASONS)

    def go_to_age_groups(self) -> AdminPage:
        """Navigate to age groups section (admin only)."""
        return self.go_to_section(AdminSection.AGE_GROUPS)

    def go_to_divisions(self) -> AdminPage:
        """Navigate to divisions section (admin only)."""
        return self.go_to_section(AdminSection.DIVISIONS)

    def go_to_leagues(self) -> AdminPage:
        """Navigate to leagues section (admin only)."""
        return self.go_to_section(AdminSection.LEAGUES)

    def go_to_invite_requests(self) -> AdminPage:
        """Navigate to invite requests section (admin only)."""
        return self.go_to_section(AdminSection.INVITE_REQUESTS)

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_loaded(self) -> bool:
        """Check if admin panel is loaded (either access denied or admin content)."""
        return self.is_visible(self.ADMIN_PANEL)

    def has_access(self) -> bool:
        """Check if user has access to admin panel (nav and content visible)."""
        # Must have the admin panel AND the nav (not just absence of access denied)
        return self.is_visible(self.ADMIN_PANEL) and self.is_visible(self.ADMIN_NAV)

    def is_access_denied(self) -> bool:
        """Check if access denied message is shown."""
        return self.is_visible(self.ACCESS_DENIED)

    def is_section_visible(self, section: AdminSection) -> bool:
        """Check if a specific section is currently visible."""
        section_selector = self.get_section_selector(section)
        return self.is_visible(section_selector)

    def is_tab_visible(self, section: AdminSection) -> bool:
        """Check if a specific tab is visible (useful for role-based tab visibility)."""
        tab_selector = self.get_tab_selector(section)
        return self.is_visible(tab_selector)

    def get_visible_tabs(self) -> list[AdminSection]:
        """Get list of visible section tabs (depends on user role)."""
        visible_tabs = []
        for section in AdminSection:
            if self.is_tab_visible(section):
                visible_tabs.append(section)
        return visible_tabs

    def get_current_section(self) -> AdminSection | None:
        """Get the currently active section."""
        for section in AdminSection:
            if self.is_section_visible(section):
                return section
        return None

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def navigate_and_verify_access(self) -> bool:
        """Navigate to admin panel and verify access."""
        self.navigate()
        self.wait_for_load()
        return self.has_access()

    def verify_admin_only_tabs(self) -> dict[str, bool]:
        """Verify which tabs are visible (useful for testing role-based access)."""
        admin_only_sections = [
            AdminSection.INVITE_REQUESTS,
            AdminSection.AGE_GROUPS,
            AdminSection.SEASONS,
            AdminSection.LEAGUES,
            AdminSection.DIVISIONS,
            AdminSection.CLUBS,
        ]

        return {
            section.value: self.is_tab_visible(section)
            for section in admin_only_sections
        }

    def verify_club_manager_tabs(self) -> dict[str, bool]:
        """Verify club manager accessible tabs."""
        club_manager_sections = [
            AdminSection.TEAMS,
            AdminSection.PLAYERS,
            AdminSection.MATCHES,
            AdminSection.INVITES,
        ]

        return {
            section.value: self.is_tab_visible(section)
            for section in club_manager_sections
        }
