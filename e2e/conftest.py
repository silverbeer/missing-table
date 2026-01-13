"""
Pytest fixtures for Playwright E2E tests.

This module provides:
- Page Object fixtures with automatic injection
- Authentication fixtures for different user roles
- Test data fixtures with Faker integration
- Screenshot and video capture on failure
- API client fixtures for data setup
- Visual regression testing utilities

Usage:
    def test_login(login_page, test_user):
        login_page.navigate()
        login_page.login(test_user.username, test_user.password)
        assert login_page.is_login_successful()
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest
from faker import Faker
from playwright.sync_api import Page, BrowserContext, Browser

# Add the test directory to path for page_objects imports
TEST_DIR = Path(__file__).parent
if str(TEST_DIR) not in sys.path:
    sys.path.insert(0, str(TEST_DIR))

# Import page objects
from page_objects import (
    LoginPage,
    StandingsPage,
    MatchesPage,
    AdminPage,
    NavigationBar,
)

if TYPE_CHECKING:
    from playwright.sync_api import Playwright

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the frontend application."""
    return os.getenv("E2E_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for the backend API."""
    return os.getenv("E2E_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def test_output_dir() -> Path:
    """Directory for test outputs (screenshots, videos, etc.)."""
    output_dir = Path(__file__).parent / "test-results"
    output_dir.mkdir(exist_ok=True)
    return output_dir


# ============================================================================
# Test User Data Classes
# ============================================================================

@dataclass
class TestUser:
    """Test user credentials and info."""
    username: str
    password: str
    role: str = "user"
    display_name: str = "Test User"
    team_id: int | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_team_manager(self) -> bool:
        return self.role == "team_manager"


# ============================================================================
# Test User Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def faker_instance() -> Faker:
    """Seeded Faker instance for reproducible test data."""
    fake = Faker()
    Faker.seed(42)
    return fake


@pytest.fixture(scope="function")
def test_user(faker_instance: Faker) -> TestUser:
    """Generate a test user with realistic data."""
    return TestUser(
        username=f"test_user_{faker_instance.random_int(1000, 9999)}",
        password="TestPassword123!",  # pragma: allowlist secret
        role="user",
        display_name=faker_instance.name(),
    )


@pytest.fixture(scope="session")
def admin_user() -> TestUser:
    """Admin user credentials for testing."""
    return TestUser(
        username=os.getenv("E2E_ADMIN_USERNAME", "e2e_admin"),
        password=os.getenv("E2E_ADMIN_PASSWORD", "AdminPassword123!"),
        role="admin",
        display_name="E2E Admin",
    )


@pytest.fixture(scope="session")
def manager_user() -> TestUser:
    """Team manager user credentials for testing."""
    return TestUser(
        username=os.getenv("E2E_MANAGER_USERNAME", "e2e_manager"),
        password=os.getenv("E2E_MANAGER_PASSWORD", "ManagerPassword123!"),
        role="team-manager",
        display_name="E2E Manager",
        team_id=1,
    )


@pytest.fixture(scope="session")
def player_user() -> TestUser:
    """Team player user credentials for testing."""
    return TestUser(
        username=os.getenv("E2E_PLAYER_USERNAME", "e2e_player"),
        password=os.getenv("E2E_PLAYER_PASSWORD", "PlayerPassword123!"),
        role="team-player",
        display_name="E2E Player",
        team_id=1,
    )


@pytest.fixture(scope="session")
def fan_user() -> TestUser:
    """Team fan user credentials for testing."""
    return TestUser(
        username=os.getenv("E2E_FAN_USERNAME", "e2e_fan"),
        password=os.getenv("E2E_FAN_PASSWORD", "FanPassword123!"),
        role="team-fan",
        display_name="E2E Fan",
    )


# ============================================================================
# Browser & Page Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    """Customize browser context with viewport and other settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "record_video_dir": "test-results/videos",
        "ignore_https_errors": True,
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }


# Note: We use pytest-playwright's built-in page fixture
# The browser_context_args fixture above configures video recording and other settings


# ============================================================================
# Page Object Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def login_page(page: Page, base_url: str) -> LoginPage:
    """Login page object fixture."""
    return LoginPage(page, base_url)


@pytest.fixture(scope="function")
def standings_page(page: Page, base_url: str) -> StandingsPage:
    """Standings page object fixture."""
    return StandingsPage(page, base_url)


@pytest.fixture(scope="function")
def matches_page(page: Page, base_url: str) -> MatchesPage:
    """Matches page object fixture."""
    return MatchesPage(page, base_url)


@pytest.fixture(scope="function")
def admin_page(page: Page, base_url: str) -> AdminPage:
    """Admin page object fixture."""
    return AdminPage(page, base_url)


@pytest.fixture(scope="function")
def nav_bar(page: Page) -> NavigationBar:
    """Navigation bar component fixture."""
    return NavigationBar(page)


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def authenticated_page(
    page: Page,
    login_page: LoginPage,
    fan_user: TestUser
) -> Generator[Page, None, None]:
    """Page with fan user authenticated."""
    login_page.navigate()
    login_page.login(fan_user.username, fan_user.password)

    # Wait for authentication to complete
    page.wait_for_timeout(1000)

    yield page


@pytest.fixture(scope="function")
def admin_authenticated_page(
    page: Page,
    login_page: LoginPage,
    admin_user: TestUser
) -> Generator[Page, None, None]:
    """Page with admin user authenticated."""
    login_page.navigate()
    login_page.login(admin_user.username, admin_user.password)

    # Wait for authentication to complete
    page.wait_for_timeout(1000)

    yield page


@pytest.fixture(scope="function")
def manager_authenticated_page(
    page: Page,
    login_page: LoginPage,
    manager_user: TestUser
) -> Generator[Page, None, None]:
    """Page with team manager user authenticated."""
    login_page.navigate()
    login_page.login(manager_user.username, manager_user.password)

    # Wait for authentication to complete
    page.wait_for_timeout(1000)

    yield page


# Storage state fixtures for faster authentication
@pytest.fixture(scope="session")
def admin_storage_state(
    browser: Browser,
    base_url: str,
    admin_user: TestUser,
    tmp_path_factory
) -> Path:
    """
    Pre-authenticated storage state for admin user.
    
    This allows tests to skip the login process by reusing
    the authentication state (cookies, local storage).
    """
    storage_path = tmp_path_factory.mktemp("storage") / "admin_state.json"
    
    context = browser.new_context()
    page = context.new_page()
    
    # Perform login
    login_page = LoginPage(page, base_url)
    login_page.navigate()
    login_page.login(admin_user.username, admin_user.password)
    page.wait_for_timeout(2000)
    
    # Save storage state
    context.storage_state(path=str(storage_path))
    context.close()
    
    return storage_path


@pytest.fixture(scope="function")
def admin_context(
    browser: Browser,
    admin_storage_state: Path
) -> Generator[BrowserContext, None, None]:
    """Browser context with admin already authenticated."""
    context = browser.new_context(storage_state=str(admin_storage_state))
    yield context
    context.close()


@pytest.fixture(scope="function")
def admin_page_fast(
    admin_context: BrowserContext,
    base_url: str
) -> Generator[Page, None, None]:
    """
    Fast admin page that skips login using stored state.
    
    Use this for tests that need admin access but don't
    test the login flow itself.
    """
    page = admin_context.new_page()
    yield page
    page.close()


# ============================================================================
# API Client Fixtures (for test data setup)
# ============================================================================

@pytest.fixture(scope="session")
def api_client(api_base_url: str):
    """HTTP client for API calls during test setup."""
    import httpx
    
    client = httpx.Client(base_url=api_base_url, timeout=30.0)
    yield client
    client.close()


@pytest.fixture(scope="function")
def authenticated_api_client(api_base_url: str, admin_user: TestUser):
    """Authenticated HTTP client for API calls."""
    import httpx

    client = httpx.Client(base_url=api_base_url, timeout=30.0)

    # Login and get token
    response = client.post("/api/auth/login", json={
        "username": admin_user.username,
        "password": admin_user.password
    })

    if response.status_code == 200:
        token = response.json().get("access_token")
        client.headers["Authorization"] = f"Bearer {token}"

    yield client
    client.close()


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_team_data(faker_instance: Faker) -> dict:
    """Generate sample team data."""
    return {
        "name": f"{faker_instance.city()} FC",
        "coach": faker_instance.name(),
        "contact_email": faker_instance.email(),
        "age_group_id": 1,
        "season_id": 1,
    }


@pytest.fixture(scope="function")
def sample_match_data(faker_instance: Faker) -> dict:
    """Generate sample match data."""
    return {
        "game_date": faker_instance.date_this_year().isoformat(),
        "home_team_id": 1,
        "away_team_id": 2,
        "home_score": faker_instance.random_int(0, 5),
        "away_score": faker_instance.random_int(0, 5),
        "venue": f"{faker_instance.city()} Stadium",
        "season_id": 1,
        "age_group_id": 1,
        "game_type_id": 1,
    }


# ============================================================================
# Visual Testing Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def screenshot_on_failure(request, page: Page, test_output_dir: Path):
    """Automatically capture screenshot on test failure."""
    yield
    
    # Check if test failed
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        test_name = request.node.name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = test_output_dir / "screenshots" / f"{test_name}_{timestamp}.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"Screenshot saved: {screenshot_path}")


@pytest.fixture(scope="session")
def baseline_screenshots_dir() -> Path:
    """Directory for baseline screenshots (visual regression)."""
    baseline_dir = Path(__file__).parent / "screenshots" / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    return baseline_dir


@pytest.fixture(scope="session")
def diff_screenshots_dir() -> Path:
    """Directory for diff screenshots (visual regression)."""
    diff_dir = Path(__file__).parent / "screenshots" / "diff"
    diff_dir.mkdir(parents=True, exist_ok=True)
    return diff_dir


# ============================================================================
# Data-Driven Testing Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Directory containing test data JSON files."""
    return Path(__file__).parent / "test_data"


def load_test_data(filename: str) -> list[dict]:
    """Load test data from JSON file in test_data directory."""
    data_path = Path(__file__).parent / "test_data" / filename
    if data_path.exists():
        with open(data_path) as f:
            return json.load(f)
    return []


@pytest.fixture(scope="session")
def login_test_data() -> list[dict]:
    """Load login test scenarios."""
    return load_test_data("login_scenarios.json")


@pytest.fixture(scope="session")
def filter_test_data() -> list[dict]:
    """Load filter test scenarios."""
    return load_test_data("filter_scenarios.json")


# ============================================================================
# Performance Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def performance_metrics(page: Page) -> Generator[dict, None, None]:
    """Capture performance metrics during test."""
    metrics = {}
    
    # Enable performance metrics collection
    client = page.context.new_cdp_session(page)
    client.send("Performance.enable")
    
    yield metrics
    
    # Collect final metrics
    perf_metrics = client.send("Performance.getMetrics")
    for metric in perf_metrics.get("metrics", []):
        metrics[metric["name"]] = metric["value"]


# ============================================================================
# Pytest Hooks
# ============================================================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for screenshot on failure."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_configure(config):
    """Configure custom markers."""
    # Markers are defined in pytest.ini, but we can add dynamic ones here
    pass


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Auto-add markers based on test function names
        if "admin" in item.name.lower():
            item.add_marker(pytest.mark.admin)
        if "login" in item.name.lower():
            item.add_marker(pytest.mark.auth)
        if "standings" in item.name.lower():
            item.add_marker(pytest.mark.standings)
        if "matches" in item.name.lower():
            item.add_marker(pytest.mark.matches)


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def wait_for_api():
    """Utility to wait for API responses."""
    def _wait(page: Page, url_pattern: str, timeout: int = 5000):
        with page.expect_response(url_pattern, timeout=timeout) as response_info:
            pass
        return response_info.value
    return _wait


@pytest.fixture(scope="function")
def intercept_api():
    """Utility to intercept and mock API responses."""
    def _intercept(page: Page, url_pattern: str, response_body: dict):
        page.route(url_pattern, lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(response_body)
        ))
    return _intercept
