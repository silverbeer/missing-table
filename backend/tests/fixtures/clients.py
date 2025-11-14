"""
Test Client Utilities

This module provides utilities for creating and configuring test clients
for different test scenarios.

Usage:
    from tests.fixtures.clients import (
        create_test_client,
        create_authenticated_client,
        create_admin_client
    )
    
    # Create basic test client
    client = create_test_client()
    response = client.get("/api/teams")
    
    # Create authenticated client
    client = create_authenticated_client(user_id="test-user", role="user")
    response = client.get("/api/protected-endpoint")
    
    # Create admin client
    admin_client = create_admin_client()
    response = admin_client.post("/api/admin/teams", json=team_data)
"""

from typing import Dict, Optional
from fastapi.testclient import TestClient
from unittest.mock import patch
import os


def create_test_client(disable_security: bool = False) -> TestClient:
    """
    Create a FastAPI TestClient for testing.
    
    Args:
        disable_security: If True, disable authentication checks (default: False)
    
    Returns:
        TestClient instance
    """
    # Import here to avoid circular dependencies
    from app import app
    
    if disable_security:
        # Patch environment to disable security
        with patch.dict(os.environ, {'DISABLE_SECURITY': 'true'}):
            return TestClient(app)
    else:
        return TestClient(app)


def create_authenticated_client(
    user_id: str = "test-user-001",
    email: str = "user@test.com",
    role: str = "user",
    token: Optional[str] = None
) -> TestClient:
    """
    Create an authenticated test client with mock JWT token.
    
    Args:
        user_id: User ID for the test user
        email: Email for the test user
        role: User role (user, team_manager, admin)
        token: Custom JWT token (optional, will generate mock token if not provided)
    
    Returns:
        TestClient instance with authentication headers
    """
    from app import app
    
    # Create test client
    client = TestClient(app)
    
    # Generate mock token if not provided
    if token is None:
        # This is a simplified mock token for testing
        # In real tests, you might want to generate a proper JWT
        token = f"mock_jwt_{user_id}_{role}"
    
    # Add default authorization header to client
    client.headers.update({
        "Authorization": f"Bearer {token}"
    })
    
    return client


def create_admin_client(
    user_id: str = "test-admin-001",
    email: str = "admin@test.com"
) -> TestClient:
    """
    Create an authenticated admin test client.
    
    Args:
        user_id: Admin user ID
        email: Admin email
    
    Returns:
        TestClient instance with admin authentication
    """
    return create_authenticated_client(
        user_id=user_id,
        email=email,
        role="admin"
    )


def create_team_manager_client(
    user_id: str = "test-manager-001",
    email: str = "manager@test.com"
) -> TestClient:
    """
    Create an authenticated team manager test client.
    
    Args:
        user_id: Team manager user ID
        email: Team manager email
    
    Returns:
        TestClient instance with team_manager authentication
    """
    return create_authenticated_client(
        user_id=user_id,
        email=email,
        role="team_manager"
    )


def add_auth_headers(
    client: TestClient,
    token: Optional[str] = None,
    user_id: str = "test-user",
    role: str = "user"
) -> TestClient:
    """
    Add authentication headers to an existing test client.
    
    Args:
        client: Existing TestClient instance
        token: JWT token (optional, will generate mock token if not provided)
        user_id: User ID
        role: User role
    
    Returns:
        TestClient with updated headers
    """
    if token is None:
        token = f"mock_jwt_{user_id}_{role}"
    
    client.headers.update({
        "Authorization": f"Bearer {token}"
    })
    
    return client


def remove_auth_headers(client: TestClient) -> TestClient:
    """
    Remove authentication headers from a test client.
    
    Args:
        client: TestClient instance
    
    Returns:
        TestClient with auth headers removed
    """
    if "Authorization" in client.headers:
        del client.headers["Authorization"]
    
    return client


def create_client_with_headers(headers: Dict[str, str]) -> TestClient:
    """
    Create test client with custom headers.
    
    Args:
        headers: Dictionary of HTTP headers
    
    Returns:
        TestClient instance with custom headers
    """
    from app import app
    
    client = TestClient(app)
    client.headers.update(headers)
    
    return client


# Example usage patterns for documentation
if __name__ == "__main__":
    # Basic client
    client = create_test_client()
    
    # Authenticated user client
    user_client = create_authenticated_client(
        user_id="test-user-123",
        email="testuser@example.com",
        role="user"
    )
    
    # Admin client
    admin_client = create_admin_client()
    
    # Team manager client
    manager_client = create_team_manager_client()
    
    # Client with custom headers
    custom_client = create_client_with_headers({
        "X-Custom-Header": "test-value",
        "User-Agent": "test-agent"
    })
    
    print("Test clients created successfully")
