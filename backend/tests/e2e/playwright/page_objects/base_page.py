"""
Base Page Object class providing common functionality for all page objects.

This module implements:
- Smart waiting strategies with configurable timeouts
- Screenshot capture utilities
- Common element interaction methods
- Error handling and logging
- Retry mechanisms for flaky elements
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from pathlib import Path
from datetime import datetime

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator, ElementHandle

logger = logging.getLogger(__name__)


class Component:
    """
    Base class for reusable UI components.
    
    Components are UI elements that appear on multiple pages,
    such as navigation bars, modals, data tables, etc.
    
    Usage:
        class DataTable(Component):
            def __init__(self, page, container_selector):
                super().__init__(page)
                self.container = page.locator(container_selector)
                
            def get_row_count(self):
                return self.container.locator("tr").count()
    """
    
    def __init__(self, page: Page) -> None:
        self.page = page
        self._timeout = 10000  # Default timeout in ms

    def set_timeout(self, timeout_ms: int) -> Component:
        """Set custom timeout for this component."""
        self._timeout = timeout_ms
        return self

    def wait_for_animation(self, ms: int = 300) -> None:
        """Wait for CSS animations to complete."""
        self.page.wait_for_timeout(ms)


class BasePage:
    """
    Base class for all Page Objects in the test framework.
    
    Features:
    - Automatic URL validation
    - Smart waiting with configurable strategies
    - Screenshot capture utilities
    - Common interaction methods with error handling
    - Retry mechanisms for flaky elements
    
    Usage:
        class LoginPage(BasePage):
            URL_PATH = "/login"
            
            def __init__(self, page):
                super().__init__(page)
                self.email_input = page.locator("#email")
                self.password_input = page.locator("#password")
                self.submit_button = page.locator("button[type='submit']")
    """
    
    # Override in subclasses
    URL_PATH: str = "/"
    PAGE_TITLE: str = ""
    LOAD_INDICATOR: str = ""  # Selector for element that indicates page is loaded
    
    def __init__(self, page: Page, base_url: str = "http://localhost:8080") -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._timeout = 30000  # Default timeout in ms
        self._screenshot_dir = Path(__file__).parent.parent / "screenshots"
        self._screenshot_dir.mkdir(exist_ok=True)

    # =========================================================================
    # Navigation
    # =========================================================================

    def navigate(self) -> BasePage:
        """Navigate to this page's URL."""
        url = f"{self.base_url}{self.URL_PATH}"
        logger.info(f"Navigating to {url}")
        self.page.goto(url, wait_until="networkidle")
        self.wait_for_load()
        return self

    def is_current_page(self) -> bool:
        """Check if browser is currently on this page."""
        current_url = self.page.url
        expected = f"{self.base_url}{self.URL_PATH}"
        return current_url.startswith(expected)

    def get_current_url(self) -> str:
        """Get the current page URL."""
        return self.page.url

    def refresh(self) -> BasePage:
        """Refresh the current page."""
        self.page.reload(wait_until="networkidle")
        self.wait_for_load()
        return self

    def go_back(self) -> None:
        """Navigate back in browser history."""
        self.page.go_back(wait_until="networkidle")

    def go_forward(self) -> None:
        """Navigate forward in browser history."""
        self.page.go_forward(wait_until="networkidle")

    # =========================================================================
    # Waiting Strategies
    # =========================================================================

    def wait_for_load(self) -> BasePage:
        """Wait for page to be fully loaded."""
        logger.debug(f"Waiting for page load: {self.__class__.__name__}")

        # Wait for network to be idle
        self.page.wait_for_load_state("networkidle", timeout=self._timeout)

        # Wait for load indicator if specified
        if self.LOAD_INDICATOR:
            self.page.wait_for_selector(
                self.LOAD_INDICATOR,
                state="visible",
                timeout=self._timeout
            )

        # Verify title if specified (using expect to avoid CSP eval issues)
        if self.PAGE_TITLE:
            from playwright.sync_api import expect
            expect(self.page).to_have_title(re.compile(self.PAGE_TITLE), timeout=self._timeout)

        return self

    def wait_for_element(
        self,
        selector: str,
        state: str = "visible",
        timeout: int | None = None
    ) -> Locator:
        """
        Wait for element with specified state.
        
        Args:
            selector: CSS selector or text selector
            state: One of 'attached', 'detached', 'visible', 'hidden'
            timeout: Custom timeout in ms
            
        Returns:
            Locator for the element
        """
        timeout = timeout or self._timeout
        return self.page.wait_for_selector(selector, state=state, timeout=timeout)

    def wait_for_text(self, text: str, timeout: int | None = None) -> None:
        """Wait for specific text to appear on page."""
        timeout = timeout or self._timeout
        self.page.wait_for_selector(f"text={text}", timeout=timeout)

    def wait_for_text_gone(self, text: str, timeout: int | None = None) -> None:
        """Wait for specific text to disappear from page."""
        timeout = timeout or self._timeout
        self.page.wait_for_selector(f"text={text}", state="hidden", timeout=timeout)

    def wait_for_network_idle(self, timeout: int | None = None) -> None:
        """Wait for all network requests to complete."""
        timeout = timeout or self._timeout
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def wait_for_api_response(
        self,
        url_pattern: str,
        timeout: int | None = None
    ) -> Any:
        """
        Wait for a specific API response.
        
        Args:
            url_pattern: URL pattern to match (e.g., "**/api/standings")
            timeout: Custom timeout in ms
            
        Returns:
            Response object
        """
        timeout = timeout or self._timeout
        with self.page.expect_response(url_pattern, timeout=timeout) as response_info:
            pass
        return response_info.value

    # =========================================================================
    # Element Interactions with Smart Waiting
    # =========================================================================

    def click(self, selector: str, force: bool = False) -> None:
        """Click element with automatic waiting."""
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout)
        locator.click(force=force)

    def fill(self, selector: str, value: str, clear: bool = True) -> None:
        """Fill input with value, optionally clearing first."""
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout)
        if clear:
            locator.clear()
        locator.fill(value)

    def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        """Type text character by character (useful for autocomplete)."""
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout)
        locator.type(text, delay=delay)

    def select_option(self, selector: str, value: str | None = None, label: str | None = None) -> None:
        """Select option from dropdown."""
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout)
        if value:
            locator.select_option(value=value)
        elif label:
            locator.select_option(label=label)

    def check(self, selector: str) -> None:
        """Check a checkbox."""
        locator = self.page.locator(selector)
        locator.check()

    def uncheck(self, selector: str) -> None:
        """Uncheck a checkbox."""
        locator = self.page.locator(selector)
        locator.uncheck()

    def hover(self, selector: str) -> None:
        """Hover over element."""
        locator = self.page.locator(selector)
        locator.hover()

    # =========================================================================
    # Element State Queries
    # =========================================================================

    def is_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        return self.page.locator(selector).is_visible()

    def is_enabled(self, selector: str) -> bool:
        """Check if element is enabled."""
        return self.page.locator(selector).is_enabled()

    def is_checked(self, selector: str) -> bool:
        """Check if checkbox/radio is checked."""
        return self.page.locator(selector).is_checked()

    def get_text(self, selector: str) -> str:
        """Get text content of element."""
        return self.page.locator(selector).inner_text()

    def get_value(self, selector: str) -> str:
        """Get value of input element."""
        return self.page.locator(selector).input_value()

    def get_attribute(self, selector: str, attribute: str) -> str | None:
        """Get attribute value of element."""
        return self.page.locator(selector).get_attribute(attribute)

    def count_elements(self, selector: str) -> int:
        """Count elements matching selector."""
        return self.page.locator(selector).count()

    def get_all_texts(self, selector: str) -> list[str]:
        """Get text content of all matching elements."""
        return self.page.locator(selector).all_inner_texts()

    # =========================================================================
    # Screenshot & Visual Testing
    # =========================================================================

    def take_screenshot(self, name: str | None = None) -> Path:
        """
        Take a screenshot of the current page.
        
        Args:
            name: Custom name for screenshot (without extension)
            
        Returns:
            Path to saved screenshot
        """
        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{self.__class__.__name__}_{timestamp}"
        
        path = self._screenshot_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)
        logger.info(f"Screenshot saved: {path}")
        return path

    def take_element_screenshot(self, selector: str, name: str | None = None) -> Path:
        """Take screenshot of specific element."""
        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{self.__class__.__name__}_element_{timestamp}"
        
        path = self._screenshot_dir / f"{name}.png"
        self.page.locator(selector).screenshot(path=str(path))
        logger.info(f"Element screenshot saved: {path}")
        return path

    # =========================================================================
    # Keyboard Actions
    # =========================================================================

    def press_key(self, key: str) -> None:
        """Press a keyboard key."""
        self.page.keyboard.press(key)

    def press_enter(self) -> None:
        """Press Enter key."""
        self.press_key("Enter")

    def press_escape(self) -> None:
        """Press Escape key."""
        self.press_key("Escape")

    def press_tab(self) -> None:
        """Press Tab key."""
        self.press_key("Tab")

    # =========================================================================
    # Assertions with Better Error Messages
    # =========================================================================

    def expect_text(self, text: str, timeout: int | None = None) -> None:
        """Assert text is present on page."""
        timeout = timeout or self._timeout
        try:
            self.page.wait_for_selector(f"text={text}", timeout=timeout)
        except Exception as e:
            self.take_screenshot(f"expect_text_failed_{text[:20]}")
            raise AssertionError(f"Expected text '{text}' not found on page") from e

    def expect_no_text(self, text: str, timeout: int | None = None) -> None:
        """Assert text is not present on page."""
        timeout = timeout or self._timeout
        try:
            self.page.wait_for_selector(f"text={text}", state="hidden", timeout=timeout)
        except Exception as e:
            self.take_screenshot(f"expect_no_text_failed_{text[:20]}")
            raise AssertionError(f"Text '{text}' should not be on page") from e

    def expect_url(self, url_pattern: str, timeout: int | None = None) -> None:
        """Assert current URL matches pattern."""
        timeout = timeout or self._timeout
        try:
            self.page.wait_for_url(url_pattern, timeout=timeout)
        except Exception as e:
            current_url = self.page.url
            self.take_screenshot("expect_url_failed")
            raise AssertionError(
                f"Expected URL matching '{url_pattern}', got '{current_url}'"
            ) from e

    def expect_title(self, title: str, timeout: int | None = None) -> None:
        """Assert page title matches."""
        timeout = timeout or self._timeout
        try:
            self.page.wait_for_function(
                f"document.title === '{title}'",
                timeout=timeout
            )
        except Exception as e:
            actual_title = self.page.title()
            self.take_screenshot("expect_title_failed")
            raise AssertionError(
                f"Expected title '{title}', got '{actual_title}'"
            ) from e

    # =========================================================================
    # Utilities
    # =========================================================================

    def set_timeout(self, timeout_ms: int) -> BasePage:
        """Set custom timeout for this page instance."""
        self._timeout = timeout_ms
        return self

    def execute_script(self, script: str) -> Any:
        """Execute JavaScript in page context."""
        return self.page.evaluate(script)

    def scroll_to_element(self, selector: str) -> None:
        """Scroll element into view."""
        self.page.locator(selector).scroll_into_view_if_needed()

    def scroll_to_top(self) -> None:
        """Scroll to top of page."""
        self.execute_script("window.scrollTo(0, 0)")

    def scroll_to_bottom(self) -> None:
        """Scroll to bottom of page."""
        self.execute_script("window.scrollTo(0, document.body.scrollHeight)")

    def get_local_storage(self, key: str) -> str | None:
        """Get value from localStorage."""
        return self.execute_script(f"localStorage.getItem('{key}')")

    def set_local_storage(self, key: str, value: str) -> None:
        """Set value in localStorage."""
        self.execute_script(f"localStorage.setItem('{key}', '{value}')")

    def clear_local_storage(self) -> None:
        """Clear all localStorage."""
        self.execute_script("localStorage.clear()")

    def get_session_storage(self, key: str) -> str | None:
        """Get value from sessionStorage."""
        return self.execute_script(f"sessionStorage.getItem('{key}')")

    def set_session_storage(self, key: str, value: str) -> None:
        """Set value in sessionStorage."""
        self.execute_script(f"sessionStorage.setItem('{key}', '{value}')")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} url='{self.URL_PATH}'>"
