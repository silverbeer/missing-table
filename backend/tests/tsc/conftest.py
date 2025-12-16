"""
TSC Journey Tests - Shared Fixtures.

Provides module-scoped fixtures for the TSC test journey:
- tsc_config: Configuration with prefixes and names
- entity_registry: Shared entity tracking across all test phases
- tsc_client: API client wrapper with entity tracking

Usage:
    Run full suite: pytest tests/tsc/ -v --order-dependencies
    Skip cleanup: pytest tests/tsc/ -v --ignore=tests/tsc/test_99_cleanup.py
    Cleanup only: pytest tests/tsc/test_99_cleanup.py -v

Setup:
    cp tests/tsc/.env.tsc.example tests/tsc/.env.tsc
    # Edit .env.tsc with your credentials
"""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig


# Load .env.tsc if it exists
ENV_FILE = Path(__file__).parent / ".env.tsc"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Registry file for persistence between test runs
REGISTRY_FILE = Path(__file__).parent / ".entity_registry.json"


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--skip-cleanup",
        action="store_true",
        default=False,
        help="Skip cleanup tests (leave data for UI testing)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip cleanup tests if --skip-cleanup is set."""
    if config.getoption("--skip-cleanup"):
        skip_cleanup = pytest.mark.skip(reason="--skip-cleanup option was set")
        for item in items:
            if "test_99_cleanup" in item.nodeid:
                item.add_marker(skip_cleanup)


@pytest.fixture(scope="module")
def tsc_config() -> TSCConfig:
    """
    TSC configuration fixture.

    Returns configuration with tsc_a_ prefix for pytest.
    BASE_URL can be set via environment variable.
    """
    return TSCConfig(prefix="tsc_a_")


@pytest.fixture(scope="module")
def entity_registry() -> EntityRegistry:
    """
    Entity registry fixture (module-scoped).

    Tracks all created entities for cleanup.
    Persists to file for recovery between test runs.
    """
    # Try to load existing registry
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE) as f:
                data = json.load(f)
                return EntityRegistry.from_dict(data)
        except Exception:
            pass

    return EntityRegistry()


@pytest.fixture(scope="module")
def tsc_client(tsc_config: TSCConfig, entity_registry: EntityRegistry) -> TSCClient:
    """
    TSC client fixture (module-scoped).

    Provides API client with entity tracking.
    """
    client = TSCClient(config=tsc_config, registry=entity_registry)
    yield client
    client.close()


@pytest.fixture(scope="module")
def save_registry(entity_registry: EntityRegistry):
    """
    Save registry after tests complete.

    Use as a finalizer to persist entity state.
    """
    yield

    # Save registry to file
    with open(REGISTRY_FILE, "w") as f:
        json.dump(entity_registry.to_dict(), f, indent=2)


@pytest.fixture(scope="function")
def existing_admin_credentials() -> tuple[str, str]:
    """
    Get credentials for an existing admin user.

    This is used in Phase 0 to login as an existing admin
    before creating the TSC admin user.

    Set via environment variables:
    - TSC_EXISTING_ADMIN_USERNAME (default: tom)
    - TSC_EXISTING_ADMIN_PASSWORD (default: tom123!)
    """
    username = os.getenv("TSC_EXISTING_ADMIN_USERNAME", "tom")
    password = os.getenv("TSC_EXISTING_ADMIN_PASSWORD", "tom123!")
    return username, password


def load_entity_registry() -> EntityRegistry:
    """
    Load entity registry from file (for cleanup script).

    Returns:
        EntityRegistry with persisted data, or empty registry
    """
    if REGISTRY_FILE.exists():
        try:
            with open(REGISTRY_FILE) as f:
                data = json.load(f)
                return EntityRegistry.from_dict(data)
        except Exception:
            pass
    return EntityRegistry()


def clear_entity_registry() -> None:
    """Remove the persisted entity registry file."""
    if REGISTRY_FILE.exists():
        REGISTRY_FILE.unlink()
