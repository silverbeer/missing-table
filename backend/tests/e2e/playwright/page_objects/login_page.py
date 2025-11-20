"""
Login Page Object for Missing Table authentication.

Handles:
- User login flow
- Form validation
- Error message handling
- Remember me functionality
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base_page import BasePage

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class LoginPage(BasePage):
    """
    Page Object for the Login functionality.

    Note: This app doesn't have a separate /login page. The login form
    is shown when clicking the "Login" button in the navigation bar.

    Usage:
        def test_successful_login(login_page):
            login_page.navigate()
            login_page.login("username", "password123")
            assert login_page.is_login_successful()
    """

    URL_PATH = "/"  # Login form is on the main page
    PAGE_TITLE = "Missing Table"
    LOAD_INDICATOR = None  # Don't wait for specific element on main page

    # Nav button to show login form
    NAV_LOGIN_BUTTON = "[data-testid='nav-login-button']"

    # Form selectors - using data-testid for stability
    # Note: This app uses USERNAME not email for login
    USERNAME_INPUT = "[data-testid='username-input'], #username"
    PASSWORD_INPUT = "[data-testid='password-input'], #password"
    SUBMIT_BUTTON = "[data-testid='login-button'], button[type='submit']"

    # Links
    SIGNUP_LINK = "[data-testid='signup-link']"
    LOGIN_LINK = "[data-testid='login-link']"

    # Messages
    ERROR_MESSAGE = "[data-testid='error-message'], .error-message"
    SUCCESS_MESSAGE = "[data-testid='success-message'], .success-message"

    # Form footer
    FORM_FOOTER = "[data-testid='form-footer']"

    # Loading state (button shows "Processing...")
    LOADING_INDICATOR = "button:has-text('Processing')"

    # User menu (shown after successful login)
    USER_MENU = "[data-testid='user-menu']"

    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        super().__init__(page, base_url)
        self.username = page.locator(self.USERNAME_INPUT).first
        self.password = page.locator(self.PASSWORD_INPUT).first
        self.submit = page.locator(self.SUBMIT_BUTTON).first

    def navigate(self) -> "LoginPage":
        """Navigate to main page and show login form."""
        super().navigate()
        # Click the login button in nav to show the form
        login_btn = self.page.locator(self.NAV_LOGIN_BUTTON)
        if login_btn.is_visible():
            login_btn.click()
            # Wait for form to appear
            self.page.wait_for_selector(self.USERNAME_INPUT, state="visible")
        return self

    # =========================================================================
    # Core Actions
    # =========================================================================

    def login(self, username: str, password: str) -> None:
        """
        Perform complete login flow.

        Args:
            username: Username
            password: User password
        """
        logger.info(f"Logging in as: {username}")

        self.enter_username(username)
        self.enter_password(password)
        self.click_submit()

        # Wait for either success or error
        self.page.wait_for_timeout(1000)  # Give time for response

    def enter_username(self, username: str) -> LoginPage:
        """Enter username."""
        logger.debug(f"Entering username: {username}")
        self.username.wait_for(state="visible")
        self.username.clear()
        self.username.fill(username)
        return self

    def enter_password(self, password: str) -> LoginPage:
        """Enter password."""
        logger.debug("Entering password")
        self.password.wait_for(state="visible")
        self.password.clear()
        self.password.fill(password)
        return self

    def click_submit(self) -> None:
        """Click the login submit button."""
        logger.debug("Clicking submit button")
        self.submit.wait_for(state="visible")
        self.submit.click()
        self.page.wait_for_load_state("networkidle")

    # =========================================================================
    # Navigation
    # =========================================================================

    def click_signup(self) -> None:
        """Click the signup link to show invite form."""
        logger.info("Clicking signup link")
        self.click(self.SIGNUP_LINK)

    # =========================================================================
    # State Queries
    # =========================================================================

    def is_login_successful(self) -> bool:
        """Check if login was successful by verifying user menu appears."""
        # Wait a bit for response
        self.page.wait_for_timeout(1000)

        # Check for user menu (only visible when logged in)
        user_menu_visible = self.page.locator(self.USER_MENU).is_visible()

        # Check for absence of error message
        no_error = not self.has_error_message()

        return user_menu_visible and no_error

    def has_error_message(self) -> bool:
        """Check if error message is displayed."""
        return self.page.locator(self.ERROR_MESSAGE).is_visible()

    def get_error_message(self) -> str:
        """Get the error message text."""
        error = self.page.locator(self.ERROR_MESSAGE)
        if error.is_visible():
            return error.inner_text()
        return ""

    def has_success_message(self) -> bool:
        """Check if success message is displayed."""
        return self.page.locator(self.SUCCESS_MESSAGE).is_visible()

    def get_success_message(self) -> str:
        """Get the success message text."""
        success = self.page.locator(self.SUCCESS_MESSAGE)
        if success.is_visible():
            return success.inner_text()
        return ""

    def is_loading(self) -> bool:
        """Check if login is in progress (loading state)."""
        return self.page.locator(self.LOADING_INDICATOR).is_visible()

    def is_submit_enabled(self) -> bool:
        """Check if submit button is enabled."""
        return self.submit.is_enabled()

    # =========================================================================
    # Form Validation
    # =========================================================================

    def get_username_validation_message(self) -> str:
        """Get browser validation message for username field."""
        return self.username.evaluate("el => el.validationMessage")

    def get_password_validation_message(self) -> str:
        """Get browser validation message for password field."""
        return self.password.evaluate("el => el.validationMessage")

    def is_username_valid(self) -> bool:
        """Check if username field passes validation."""
        return self.username.evaluate("el => el.checkValidity()")

    def is_password_valid(self) -> bool:
        """Check if password field passes validation."""
        return self.password.evaluate("el => el.checkValidity()")

    def clear_form(self) -> LoginPage:
        """Clear all form fields."""
        self.username.clear()
        self.password.clear()
        return self

    # =========================================================================
    # Testing Utilities
    # =========================================================================

    def submit_with_enter(self) -> None:
        """Submit form using Enter key."""
        self.password.press("Enter")
        self.page.wait_for_load_state("networkidle")

    def tab_through_form(self) -> None:
        """Tab through all form fields (accessibility testing)."""
        self.username.focus()
        self.page.keyboard.press("Tab")  # To password
        self.page.keyboard.press("Tab")  # To submit
