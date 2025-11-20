"""
Visual Regression Tests for Missing Table.

These tests capture and compare screenshots to detect
unintended visual changes across releases.

Demonstrates:
- Visual regression testing patterns
- Baseline management
- Element-specific screenshots
- Viewport-specific comparisons
"""

import pytest
from pathlib import Path
from playwright.sync_api import Page

from page_objects import StandingsPage, LoginPage
from fixtures.visual_regression import VisualRegression


@pytest.fixture(scope="function")
def visual_regression(
    page: Page,
    baseline_screenshots_dir: Path,
    diff_screenshots_dir: Path
) -> VisualRegression:
    """Visual regression testing fixture."""
    return VisualRegression(
        page=page,
        baseline_dir=baseline_screenshots_dir,
        diff_dir=diff_screenshots_dir,
        threshold=0.02  # 2% pixel difference allowed
    )


class TestVisualRegression:
    """Visual regression test suite."""

    @pytest.mark.visual
    @pytest.mark.smoke
    def test_homepage_visual(
        self,
        standings_page: StandingsPage,
        visual_regression: VisualRegression
    ):
        """
        Test homepage visual appearance.
        
        Captures full-page screenshot and compares to baseline.
        """
        # Arrange
        standings_page.navigate()
        standings_page.wait_for_load()
        
        # Assert
        assert visual_regression.compare("homepage_full"), \
            "Homepage visual should match baseline"

    @pytest.mark.visual
    def test_login_page_visual(
        self,
        login_page: LoginPage,
        visual_regression: VisualRegression
    ):
        """Test login page visual appearance."""
        # Arrange
        login_page.navigate()
        
        # Assert
        assert visual_regression.compare("login_page"), \
            "Login page visual should match baseline"

    @pytest.mark.visual
    def test_standings_table_visual(
        self,
        standings_page: StandingsPage,
        visual_regression: VisualRegression
    ):
        """
        Test standings table component visual.
        
        Element-specific screenshot for focused testing.
        """
        # Arrange
        standings_page.navigate()
        standings_page.wait_for_load()
        
        # Assert - Just the table element
        assert visual_regression.compare(
            "standings_table",
            full_page=False,
            element=standings_page.STANDINGS_TABLE
        ), "Standings table visual should match baseline"

    @pytest.mark.visual
    def test_login_error_state_visual(
        self,
        login_page: LoginPage,
        visual_regression: VisualRegression
    ):
        """
        Test login page with error state.
        
        Captures UI in error state for visual verification.
        """
        # Arrange
        login_page.navigate()
        login_page.login("invalid@example.com", "wrongpassword")
        
        # Assert
        if login_page.has_error_message():
            assert visual_regression.compare("login_error_state"), \
                "Login error state visual should match baseline"

    @pytest.mark.visual
    @pytest.mark.parametrize("viewport,name", [
        ({"width": 1920, "height": 1080}, "desktop"),
        ({"width": 768, "height": 1024}, "tablet"),
        ({"width": 375, "height": 667}, "mobile"),
    ])
    def test_responsive_visual(
        self,
        page: Page,
        standings_page: StandingsPage,
        visual_regression: VisualRegression,
        viewport: dict,
        name: str
    ):
        """
        Test visual appearance at different viewports.
        
        Responsive design visual verification.
        """
        # Arrange
        page.set_viewport_size(viewport)
        standings_page.navigate()
        standings_page.wait_for_load()
        
        # Assert
        assert visual_regression.compare(f"homepage_{name}"), \
            f"Homepage at {name} viewport should match baseline"


class TestDarkModeVisual:
    """Visual regression tests for dark mode (if implemented)."""

    @pytest.mark.visual
    @pytest.mark.skip(reason="Dark mode not yet implemented")
    def test_homepage_dark_mode(
        self,
        page: Page,
        standings_page: StandingsPage,
        visual_regression: VisualRegression
    ):
        """Test homepage in dark mode."""
        # Arrange - Enable dark mode via preference
        page.emulate_media(color_scheme="dark")
        standings_page.navigate()
        
        # Assert
        assert visual_regression.compare("homepage_dark"), \
            "Homepage dark mode visual should match baseline"
