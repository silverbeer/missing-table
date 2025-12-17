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

Environment-aware registry (Option B + D):
    - Registry files are environment-specific: .entity_registry.{env}.json
    - base_url is stored in registry to detect mismatches
    - Switching environments creates a fresh registry automatically
"""

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from tests.fixtures.tsc import EntityRegistry, TSCClient, TSCConfig, get_env_key


# Load .env.tsc if it exists (check multiple locations)
ENV_FILES = [
    Path(__file__).parent / ".env.tsc",                    # tests/tsc/.env.tsc
    Path(__file__).parent.parent / ".env.tsc",             # tests/.env.tsc
    Path(__file__).parent.parent.parent / ".env.tsc",      # backend/.env.tsc
]

for env_file in ENV_FILES:
    if env_file.exists():
        load_dotenv(env_file)
        break


def get_registry_file() -> Path:
    """
    Get environment-specific registry file path (Option D).

    Returns paths like:
        .entity_registry.local.json
        .entity_registry.missingtable.com.json
        .entity_registry.dev.missingtable.com.json
    """
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    env_key = get_env_key(base_url)
    return Path(__file__).parent / f".entity_registry.{env_key}.json"


# Legacy registry file for migration
LEGACY_REGISTRY_FILE = Path(__file__).parent / ".entity_registry.json"


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

    Environment-aware (Option B + D):
    - Uses environment-specific registry files
    - Validates base_url matches current environment
    - Creates fresh registry if environment changed
    """
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    registry_file = get_registry_file()

    # Try to load existing registry
    if registry_file.exists():
        try:
            with open(registry_file) as f:
                data = json.load(f)
                registry = EntityRegistry.from_dict(data)

                # Option B: Validate base_url matches
                stored_url = registry.base_url
                if stored_url and stored_url != base_url:
                    print(f"\n⚠️  Environment mismatch detected!")
                    print(f"   Registry was created for: {stored_url}")
                    print(f"   Current environment:      {base_url}")
                    print(f"   Starting fresh registry for {base_url}")
                    registry = EntityRegistry(base_url=base_url)
                elif not stored_url:
                    # Upgrade old registry without base_url
                    registry.base_url = base_url
                    print(f"   Upgraded registry to track base_url: {base_url}")

                return registry
        except Exception as e:
            print(f"⚠️  Failed to load registry: {e}")

    # Check for legacy registry and warn
    if LEGACY_REGISTRY_FILE.exists():
        print(f"\n⚠️  Found legacy registry file: {LEGACY_REGISTRY_FILE}")
        print(f"   This file is no longer used. Delete it if no longer needed.")
        print(f"   New registry: {registry_file}")

    return EntityRegistry(base_url=base_url)


@pytest.fixture(scope="module")
def tsc_client(tsc_config: TSCConfig, entity_registry: EntityRegistry) -> TSCClient:
    """
    TSC client fixture (module-scoped).

    Provides API client with entity tracking.
    Automatically saves registry on teardown for persistence between runs.
    Uses environment-specific registry file (Option D).
    """
    client = TSCClient(config=tsc_config, registry=entity_registry)
    yield client
    client.close()

    # Save registry to environment-specific file on teardown
    registry_file = get_registry_file()
    with open(registry_file, "w") as f:
        json.dump(entity_registry.to_dict(), f, indent=2)
    print(f"\n📁 Registry saved to: {registry_file.name}")


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

    Uses environment-specific registry file (Option D).

    Returns:
        EntityRegistry with persisted data, or empty registry
    """
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    registry_file = get_registry_file()

    if registry_file.exists():
        try:
            with open(registry_file) as f:
                data = json.load(f)
                registry = EntityRegistry.from_dict(data)

                # Validate environment matches
                if registry.base_url and registry.base_url != base_url:
                    print(f"⚠️  Registry environment mismatch!")
                    print(f"   Registry: {registry.base_url}")
                    print(f"   Current:  {base_url}")
                    return EntityRegistry(base_url=base_url)

                return registry
        except Exception as e:
            print(f"⚠️  Failed to load registry: {e}")

    return EntityRegistry(base_url=base_url)


def clear_entity_registry() -> None:
    """
    Remove the persisted entity registry file for current environment.

    Uses environment-specific registry file (Option D).
    """
    registry_file = get_registry_file()
    if registry_file.exists():
        registry_file.unlink()
        print(f"🗑️  Cleared registry: {registry_file.name}")


def clear_all_registries() -> None:
    """Remove ALL entity registry files (all environments)."""
    registry_dir = Path(__file__).parent
    for registry_file in registry_dir.glob(".entity_registry.*.json"):
        registry_file.unlink()
        print(f"🗑️  Cleared: {registry_file.name}")

    # Also clear legacy file
    if LEGACY_REGISTRY_FILE.exists():
        LEGACY_REGISTRY_FILE.unlink()
        print(f"🗑️  Cleared legacy: {LEGACY_REGISTRY_FILE.name}")
