"""
Pytest configuration and fixtures for the sports league backend tests.

This file provides shared fixtures and configuration for all test layers:
- Unit tests (tests/unit/): Fast, isolated component tests
- Integration tests (tests/integration/): Component interaction tests
- Contract tests (tests/contract/): API contract validation
- E2E tests (tests/e2e/): End-to-end user journey tests
- Smoke tests (tests/smoke/): Quick sanity checks for deployments

All tests use markers to enable selective test execution:
    pytest -m unit           # Run only unit tests
    pytest -m integration    # Run only integration tests
    pytest -m contract       # Run only contract tests
    pytest -m e2e            # Run only e2e tests
    pytest -m smoke          # Run only smoke tests
"""

import asyncio
import os
import time

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from unittest.mock import patch
from faker import Faker

# Load environment variables - prioritize test environment
# Priority: .env.test > .env.e2e > .env
load_dotenv()  # Load .env first (lowest priority)
load_dotenv("../.env.test", override=True)  # Override with test config
load_dotenv("../.env.e2e", override=True)  # Override with e2e config when running e2e tests


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Base URL Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def base_api_url():
    """Base URL for API endpoints."""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_frontend_url():
    """Base URL for frontend application."""
    return os.getenv("FRONTEND_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def supabase_url():
    """Supabase instance URL."""
    return os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")


@pytest.fixture(scope="session")
def supabase_anon_key():
    """Supabase anonymous key."""
    return os.getenv("SUPABASE_ANON_KEY", "")


@pytest.fixture(scope="session")
def supabase_service_key():
    """Supabase service role key."""
    return os.getenv("SUPABASE_SERVICE_KEY", "")


# ============================================================================
# Test Data Generation Fixtures (Faker)
# ============================================================================

@pytest.fixture(scope="session")
def faker_instance():
    """Shared Faker instance for generating realistic test data.

    Usage:
        def test_something(faker_instance):
            email = faker_instance.email()
            name = faker_instance.name()
            city = faker_instance.city()
    """
    fake = Faker()
    Faker.seed(42)  # Seed for reproducible test data
    return fake


@pytest.fixture(scope="function")
def faker_factory():
    """Factory for creating fresh Faker instances with random seeds.

    Use this when you need different data on each test run.

    Usage:
        def test_something(faker_factory):
            fake = faker_factory()
            random_email = fake.email()
    """
    def _create_faker(seed=None):
        fake = Faker()
        if seed is not None:
            Faker.seed(seed)
        return fake
    return _create_faker


# ============================================================================
# FastAPI Test Client Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_client():
    """Create a test client for the FastAPI application."""
    from app import app

    # Ensure we're using the e2e Supabase instance for tests
    e2e_url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    e2e_service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # Validate we're in test mode (check for TEST_MODE environment variable)
    test_mode = os.getenv("TEST_MODE", "false").lower()
    if test_mode != "true":
        pytest.skip("Tests must run in TEST_MODE=true environment. Ensure .env.e2e is loaded.")
    
    os.environ["SUPABASE_URL"] = e2e_url
    os.environ["SUPABASE_SERVICE_KEY"] = e2e_service_key

    with TestClient(app) as client:
        yield client


# ============================================================================
# Database Client Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def supabase_client():
    """Create a Supabase client for direct database operations."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    # Validate we're in test mode
    test_mode = os.getenv("TEST_MODE", "false").lower()
    if test_mode != "true":
        pytest.skip("Tests must run in TEST_MODE=true environment. Ensure .env.e2e is loaded.")

    if not key:
        pytest.skip("SUPABASE_SERVICE_KEY environment variable not set")

    client = create_client(url, key)
    return client


@pytest.fixture(scope="session")
def enhanced_dao():
    """Create an enhanced DAO instance for testing."""
    from dao.match_dao import MatchDAO, SupabaseConnection

    conn = SupabaseConnection()
    dao = MatchDAO(conn)
    return dao


# ============================================================================
# Sample Test Data Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_team_data():
    """Sample team data for testing."""
    return {
        "name": "Test Team FC",
        "city": "Test City",
        "age_group_id": 1,  # Assuming U13 exists
        "season_id": 1,  # Assuming 2024-2025 exists
        "coach": "Test Coach",
        "contact_email": "test@example.com",
    }


@pytest.fixture(scope="function")
def sample_game_data():
    """Sample game data for testing."""
    return {
        "game_date": "2024-03-15",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_score": 2,
        "away_score": 1,
        "season_id": 1,
        "age_group_id": 1,
        "game_type_id": 1,  # Assuming regular season exists
        "venue": "Test Stadium",
    }


@pytest.fixture(scope="function")
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "display_name": "Test User"
    }


@pytest.fixture(scope="function") 
def sample_admin_data():
    """Sample admin user data for testing."""
    return {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "display_name": "Admin User"
    }


@pytest.fixture(scope="session")
def test_database_populated(supabase_client):
    """Ensure test database has basic reference data."""
    try:
        # Check if we have basic reference data
        age_groups = supabase_client.table('age_groups').select('*').execute()
        seasons = supabase_client.table('seasons').select('*').execute()
        game_types = supabase_client.table('game_types').select('*').execute()
        
        has_data = (
            len(age_groups.data) > 0 and 
            len(seasons.data) > 0 and 
            len(game_types.data) > 0
        )
        
        return has_data
    except Exception:
        return False


# ============================================================================
# Authentication & Authorization Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def auth_headers():
    """Mock authentication headers for testing."""
    return {
        "Authorization": "Bearer mock_token_for_testing"
    }


@pytest.fixture(scope="function")
def mock_security_disabled():
    """Mock environment with security disabled."""
    with patch.dict(os.environ, {'DISABLE_SECURITY': 'true'}):
        yield


@pytest.fixture(scope="function")
def clean_test_data():
    """Fixture to ensure clean test data state."""
    # This would be used for tests that modify data
    # For now, it's a placeholder since most tests are read-only
    yield
    # Cleanup would go here if needed


# ============================================================================
# Pytest Hooks & Configuration
# ============================================================================

def pytest_runtest_setup(item):
    """Check if Supabase is required and available before running specific tests."""
    # Check if test is marked as integration or e2e
    if item.get_closest_marker("integration") or item.get_closest_marker("e2e"):
        import httpx
        import inspect

        # Check if test uses TestClient (in-memory) - these don't need Supabase
        # Tests that use TestClient typically don't need a real database connection
        test_func = item.function
        if hasattr(test_func, '__code__'):
            # Check if test uses test_client fixture (which uses TestClient)
            sig = inspect.signature(test_func)
            if 'test_client' in sig.parameters:
                # Test uses TestClient, skip Supabase check
                return

        url = os.getenv("SUPABASE_URL", "http://127.0.0.1:54321")
        
        # Validate we're in test mode
        test_mode = os.getenv("TEST_MODE", "false").lower()
        if test_mode != "true":
            pytest.skip("Tests must run in TEST_MODE=true environment. Ensure .env.e2e is loaded.")

        try:
            response = httpx.get(f"{url}/rest/v1/", timeout=2.0)
            if response.status_code not in [200, 404]:  # 404 is OK for REST endpoint
                pytest.skip(f"E2E Supabase not accessible at {url}")
        except Exception as e:
            pytest.skip(f"E2E Supabase not running: {e}. Start with: ./scripts/e2e-db-setup.sh")


@pytest.fixture(scope="function")
def admin_user_data():
    """Sample admin user data for testing."""
    return {
        "id": "admin-test-id",
        "email": "admin@example.com",
        "display_name": "Test Admin",
        "role": "admin"
    }


@pytest.fixture(scope="function")
def team_manager_user_data():
    """Sample team manager user data for testing."""
    return {
        "id": "manager-test-id",
        "email": "manager@example.com",
        "display_name": "Test Manager",
        "role": "team_manager"
    }


@pytest.fixture(scope="function")
def regular_user_data():
    """Sample regular user data for testing."""
    return {
        "id": "user-test-id",
        "email": "user@example.com", 
        "display_name": "Test User",
        "role": "user"
    }


@pytest.fixture(scope="function")
def valid_team_data():
    """Valid team data for testing team creation."""
    return {
        "name": f"Test Team {int(time.time())}",
        "city": "Test City",
        "age_group_id": 1,
        "season_id": 1,
        "coach": "Test Coach",
        "contact_email": "coach@example.com"
    }


@pytest.fixture(scope="function") 
def valid_game_data():
    """Valid game data for testing game creation."""
    return {
        "game_date": "2024-12-15",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_score": None,
        "away_score": None,
        "season_id": 1,
        "age_group_id": 1,
        "game_type_id": 1,
        "venue": "Test Stadium",
        "scheduled_time": "15:00"
    }


@pytest.fixture(scope="function")
def mock_auth_headers():
    """Mock authentication headers for different user roles."""
    return {
        "admin": {"Authorization": "Bearer mock_admin_token"},
        "team_manager": {"Authorization": "Bearer mock_manager_token"},
        "user": {"Authorization": "Bearer mock_user_token"}
    }


# ============================================================================
# Test Cleanup & Database Utilities
# ============================================================================

@pytest.fixture(scope="function")
def database_cleanup():
    """Fixture to clean up test data after tests."""
    # Setup: record initial state if needed
    yield
    # Cleanup: could add cleanup logic here if needed
    # For now, we rely on test isolation through separate test database


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
