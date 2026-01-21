"""
Navigation Bar Component for Missing Table.

This component handles the main navigation bar that appears on all pages.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base_page import Component

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class NavigationBar(Component):
    """
    Reusable navigation bar component.

    Handles:
    - Main menu navigation links
    - User authentication status
    - User dropdown menu
    - Mobile responsive menu
    """

    # Selectors - using data-testid for stability
    NAV_CONTAINER = "[data-testid='main-nav'], nav.auth-nav"

    # Brand
    NAV_BRAND = "[data-testid='nav-brand']"

    # Auth elements
    LOGIN_BUTTON = "[data-testid='nav-login-button'], .login-btn"
    USER_MENU = "[data-testid='user-menu']"
    USER_DROPDOWN = "[data-testid='user-dropdown']"
    USER_NAME = "[data-testid='user-name']"
    USER_ROLE = "[data-testid='user-role']"
    DROPDOWN_MENU = "[data-testid='dropdown-menu']"
    LOGOUT_BUTTON = "[data-testid='logout-button']"
    LOADING_BAR = "[data-testid='loading-bar']"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.container = page.locator(self.NAV_CONTAINER)

    # =========================================================================
    # Navigation Actions
    # =========================================================================

    def click_home(self) -> None:
        """Navigate to home page."""
        logger.info("Clicking Home link")
        self.page.click(self.LINK_HOME)
        self.page.wait_for_load_state("networkidle")

    def click_standings(self) -> None:
        """Navigate to standings page."""
        logger.info("Clicking Standings link")
        self.page.click(self.LINK_STANDINGS)
        self.page.wait_for_load_state("networkidle")

    def click_matches(self) -> None:
        """Navigate to matches page."""
        logger.info("Clicking Matches link")
        self.page.click(self.LINK_MATCHES)
        self.page.wait_for_load_state("networkidle")

    def click_admin(self) -> None:
        """Navigate to admin panel."""
        logger.info("Clicking Admin link")
        self.page.click(self.LINK_ADMIN)
        self.page.wait_for_load_state("networkidle")

    def click_login(self) -> None:
        """Click login button."""
        logger.info("Clicking Login button")
        self.page.click(self.LOGIN_BUTTON)

    def click_signup(self) -> None:
        """Click signup button."""
        logger.info("Clicking Sign Up button")
        self.page.click(self.SIGNUP_BUTTON)

    # =========================================================================
    # User Menu Actions
    # =========================================================================

    def open_user_menu(self) -> None:
        """Open the user dropdown menu."""
        logger.info("Opening user menu")
        self.page.click(self.USER_MENU)
        self.wait_for_animation()

    def click_logout(self) -> None:
        """Click logout from user menu."""
        logger.info("Clicking Logout")
        self.open_user_menu()
        self.page.click(self.LOGOUT_BUTTON)
        self.page.wait_for_load_state("networkidle")

    def click_profile(self) -> None:
        """Click profile link from user menu."""
        logger.info("Clicking Profile")
        self.open_user_menu()
        self.page.click(self.PROFILE_LINK)
        self.page.wait_for_load_state("networkidle")

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_logged_in(self) -> bool:
        """Check if user is logged in (user menu visible)."""
        # Try to find user menu or logout indicators
        return self.page.locator(self.USER_MENU).is_visible() or self.page.locator(self.LOGOUT_BUTTON).is_visible()

    def is_admin_visible(self) -> bool:
        """Check if Admin link is visible (admin user logged in)."""
        return self.page.locator(self.LINK_ADMIN).is_visible()

    def get_current_nav_item(self) -> str | None:
        """Get the currently active navigation item."""
        active_link = self.container.locator(".active, [aria-current='page']")
        if active_link.count() > 0:
            return active_link.inner_text()
        return None

    def get_username(self) -> str | None:
        """Get the displayed username from nav."""
        if self.is_logged_in():
            user_menu = self.page.locator(self.USER_MENU)
            return user_menu.inner_text()
        return None

    # =========================================================================
    # Mobile Menu
    # =========================================================================

    def is_mobile_view(self) -> bool:
        """Check if we're in mobile responsive view."""
        return self.page.locator(self.MOBILE_MENU_BUTTON).is_visible()

    def open_mobile_menu(self) -> None:
        """Open mobile navigation menu."""
        if self.is_mobile_view():
            logger.info("Opening mobile menu")
            self.page.click(self.MOBILE_MENU_BUTTON)
            self.wait_for_animation()

    def close_mobile_menu(self) -> None:
        """Close mobile navigation menu."""
        if self.is_mobile_view():
            # Usually clicking outside or pressing Escape
            self.page.keyboard.press("Escape")
            self.wait_for_animation()
