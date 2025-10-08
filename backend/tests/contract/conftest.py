"""Pytest configuration for contract tests."""

import os
import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from rich.console import Console

from api_client import MissingTableClient

console = Console()


def check_server_running(base_url: str) -> bool:
    """Check if the backend server is running."""
    try:
        response = httpx.get(f"{base_url}/health", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture(scope="session", autouse=True)
def verify_server_running(api_base_url: str = "http://localhost:8000"):
    """Verify server is running before contract tests start."""
    if not check_server_running(api_base_url):
        console.print("\n[bold red]❌ Backend server is not running![/bold red]\n")
        console.print(f"   Contract tests require a running server at: [cyan]{api_base_url}[/cyan]\n")
        console.print("   [bold]Please start the server first:[/bold]\n")
        console.print("   [yellow]Terminal 1:[/yellow]")
        console.print("   $ cd backend")
        console.print("   $ ./missing-table.sh dev\n")
        console.print("   [yellow]Terminal 2:[/yellow]")
        console.print("   $ cd backend")
        console.print("   $ uv run pytest tests/contract/ -m contract -v\n")
        console.print("   [dim]Or use FastAPI TestClient for tests that don't need a real server[/dim]\n")

        pytest.exit("Backend server not running. Start server and try again.", returncode=1)

    console.print(f"\n[green]✅ Server running at {api_base_url}[/green]\n")


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
    test_password = "Test123!@#"  # pragma: allowlist secret

    try:
        # Try to signup (may fail if user exists)
        client.signup(email=test_email, password=test_password, display_name="Contract Test User")
    except Exception:
        pass  # User probably exists

    # Always login to ensure we have tokens (signup doesn't auto-login)
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
