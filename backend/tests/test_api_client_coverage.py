"""
CI gate: validate api_inventory.json against FastAPI routes and client methods.

This test ensures:
1. Every FastAPI route is documented in the inventory (or explicitly excluded)
2. Every inventory endpoint has a client method
3. Every inventory endpoint has at least 1 contract test

Run: cd backend && uv run pytest tests/test_api_client_coverage.py -v
"""

import json
import os
import re
import sys

import pytest

# Add backend to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVENTORY_PATH = os.path.join(BACKEND_DIR, "api_inventory.json")

# Health/utility routes that are not under /api/
NON_API_PATHS = {"/health", "/health/full", "/metrics"}


def normalize_path(path: str) -> str:
    """Normalize path parameters for comparison."""
    return re.sub(r"\{[^}]+\}", "{param}", path)


def load_inventory():
    """Load and return the api_inventory.json."""
    with open(INVENTORY_PATH) as f:
        return json.load(f)


def get_fastapi_routes():
    """Get all (method, path) tuples from the FastAPI app."""
    from app import app

    routes = set()
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        path = route.path
        if path in NON_API_PATHS or not path.startswith("/api/"):
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.add((method, path))
    return routes


class TestApiInventoryCompleteness:
    """Test that the API inventory is complete and accurate."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.inventory = load_inventory()
        self.app_routes = get_fastapi_routes()
        self.inventory_endpoints = {
            (e["method"], e["path"]) for e in self.inventory["endpoints"]
        }
        self.excluded_endpoints = {
            (e["method"], e["path"]) for e in self.inventory["excluded_endpoints"]
        }
        self.all_documented = self.inventory_endpoints | self.excluded_endpoints

    def test_inventory_file_exists(self):
        """api_inventory.json must exist."""
        assert os.path.exists(INVENTORY_PATH), (
            "api_inventory.json not found. Run: "
            "cd backend && uv run python scripts/generate_api_inventory.py"
        )

    def test_all_routes_documented(self):
        """Every FastAPI route must appear in the inventory or excluded list."""
        undocumented = []
        for method, path in sorted(self.app_routes):
            norm = normalize_path(path)
            found = any(
                normalize_path(p) == norm and m == method
                for m, p in self.all_documented
            )
            if not found:
                undocumented.append(f"{method} {path}")

        assert not undocumented, (
            f"Routes not in api_inventory.json ({len(undocumented)}):\n"
            + "\n".join(f"  - {r}" for r in undocumented)
            + "\n\nRun: cd backend && uv run python scripts/generate_api_inventory.py"
        )

    def test_all_endpoints_have_client_method(self):
        """Every non-excluded endpoint must have a client method."""
        missing = [
            f"{e['method']} {e['path']}"
            for e in self.inventory["endpoints"]
            if not e.get("client_method")
        ]

        assert not missing, (
            f"Endpoints missing client methods ({len(missing)}):\n"
            + "\n".join(f"  - {r}" for r in missing)
            + "\n\nAdd methods to api_client/client.py"
        )

    def test_all_endpoints_have_contract_test(self):
        """Every non-excluded endpoint must have at least 1 contract test."""
        missing = []
        for e in self.inventory["endpoints"]:
            has_contract = any(t["type"] == "contract" for t in e.get("tests", []))
            if not has_contract:
                missing.append(f"{e['method']} {e['path']} ({e.get('client_method', 'no method')})")

        assert not missing, (
            f"Endpoints missing contract tests ({len(missing)}):\n"
            + "\n".join(f"  - {r}" for r in missing)
            + "\n\nAdd contract tests to tests/contract/"
        )

    def test_no_stale_inventory_entries(self):
        """Inventory entries should correspond to actual routes."""
        stale = []
        for method, path in sorted(self.inventory_endpoints):
            norm = normalize_path(path)
            found = any(
                normalize_path(p) == norm and m == method
                for m, p in self.app_routes
            )
            if not found:
                stale.append(f"{method} {path}")

        assert not stale, (
            f"Stale inventory entries (no matching route) ({len(stale)}):\n"
            + "\n".join(f"  - {r}" for r in stale)
            + "\n\nRegenerate: cd backend && uv run python scripts/generate_api_inventory.py"
        )

    def test_excluded_endpoints_have_reasons(self):
        """Every excluded endpoint must have a documented reason."""
        missing_reason = [
            f"{e['method']} {e['path']}"
            for e in self.inventory["excluded_endpoints"]
            if not e.get("reason")
        ]

        assert not missing_reason, (
            "Excluded endpoints missing reasons:\n"
            + "\n".join(f"  - {r}" for r in missing_reason)
        )
