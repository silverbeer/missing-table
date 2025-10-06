"""Pytest configuration for contract tests."""

import os

import pytest
from fastapi.testclient import TestClient

from api_client import MissingTableClient


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Get API base URL from environment or use default."""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def contract_test_client(api_base_url: str) -> TestClient:
    """Create a test client for contract tests."""
    from app import app

    return TestClient(app)


@pytest.fixture
def api_client(api_base_url: str) -> MissingTableClient:
    """Create an API client instance."""
    with MissingTableClient(base_url=api_base_url) as client:
        yield client


@pytest.fixture
def authenticated_api_client(api_base_url: str) -> MissingTableClient:
    """Create an authenticated API client."""
    client = MissingTableClient(base_url=api_base_url)

    # Create a test user and login
    test_email = f"contract_test_{os.getpid()}@example.com"
    test_password = "Test123!@#"

    try:
        # Try to signup (may fail if user exists)
        client.signup(email=test_email, password=test_password, display_name="Contract Test User")
    except Exception:
        # User probably exists, try to login
        client.login(email=test_email, password=test_password)

    yield client
    client.close()


@pytest.fixture
def admin_client(api_base_url: str) -> MissingTableClient:
    """Create an admin API client."""
    admin_email = os.getenv("ADMIN_TEST_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_TEST_PASSWORD", "admin123")

    client = MissingTableClient(base_url=api_base_url)

    try:
        client.login(email=admin_email, password=admin_password)
    except Exception as e:
        pytest.skip(f"Admin user not available: {e}")

    yield client
    client.close()
