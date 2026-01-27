#!/usr/bin/env python3
"""
Generate api_inventory.json from FastAPI routes, MissingTableClient methods, and test files.

Usage:
    cd backend && uv run python scripts/generate_api_inventory.py
"""

import ast
import json
import os
import re
import sys
from datetime import UTC, datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Excluded endpoints ---
EXCLUDED_ENDPOINTS = [
    {
        "method": "POST",
        "path": "/api/auth/oauth/callback",
        "reason": "Browser redirect flow, not suited for HTTP client",
    },
    {
        "method": "POST",
        "path": "/api/match-scraper/matches",
        "reason": "Internal scraper-to-backend ingestion",
    },
    {
        "method": "GET",
        "path": "/api/check-match",
        "reason": "Internal scraper duplicate-check",
    },
]

EXCLUDED_PATHS = {(e["method"], e["path"]) for e in EXCLUDED_ENDPOINTS}

# Health and utility endpoints not part of /api/ namespace
NON_API_PATHS = {"/health", "/health/full"}


def get_fastapi_routes():
    """Introspect FastAPI app to get all routes."""
    # Set dummy env vars so the app can be imported without a real DB connection.
    # We only need route metadata, never make actual database calls.
    for var in ("SUPABASE_URL", "SUPABASE_ANON_KEY"):
        if not os.environ.get(var):
            os.environ[var] = "https://placeholder.supabase.co"

    from app import app

    routes = []
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        path = route.path
        # Skip non-API routes
        if path in NON_API_PATHS:
            continue
        if not path.startswith("/api/"):
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.append({"method": method, "path": path})
    return sorted(routes, key=lambda r: (r["path"], r["method"]))


def get_client_method_map():
    """Parse client.py AST to build path -> method_name mapping."""
    client_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "api_client",
        "client.py",
    )
    with open(client_path) as f:
        source = f.read()

    tree = ast.parse(source)

    method_map = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            continue

        # Look for _request or _request_multipart calls to find the path
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute) and func.attr in ("_request", "_request_multipart"):
                    if len(child.args) >= 2:
                        http_method_node = child.args[0]
                        path_node = child.args[1]

                        http_method = _extract_string(http_method_node)
                        path_str = _extract_path_pattern(path_node)

                        if http_method and path_str:
                            method_map[(http_method, path_str)] = node.name
    return method_map


def _extract_string(node):
    """Extract string value from AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_path_pattern(node):
    """Extract path pattern from AST node, converting f-strings to path templates."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string — reconstruct with {param} placeholders
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                # Extract variable name for the placeholder
                if isinstance(value.value, ast.Name):
                    parts.append(f"{{{value.value.id}}}")
                elif isinstance(value.value, ast.Attribute):
                    parts.append(f"{{{value.value.attr}}}")
                else:
                    parts.append("{param}")
        return "".join(parts)
    return None


def normalize_path(path: str) -> str:
    """Normalize path parameters: /api/teams/{team_id} -> /api/teams/{team_id}."""
    return re.sub(r"\{[^}]+\}", "{param}", path)


def find_tests_for_method(method_name: str, test_dir: str) -> list[dict]:
    """Scan test files for references to a client method."""
    tests = []
    if not os.path.isdir(test_dir):
        return tests

    for root, _dirs, files in os.walk(test_dir):
        for fname in files:
            if not fname.startswith("test_") or not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, os.path.dirname(test_dir))

            with open(fpath) as f:
                try:
                    content = f.read()
                except Exception:
                    continue

            # Check if this test file references the method
            if method_name not in content:
                continue

            # Determine test type from directory
            if "/contract/" in fpath:
                test_type = "contract"
            elif "/tsc/" in fpath:
                test_type = "journey"
            elif "/integration/" in fpath:
                test_type = "integration"
            else:
                test_type = "unit"

            # Find specific test functions that reference this method
            for match in re.finditer(r"def (test_\w+)", content):
                test_name = match.group(1)
                # Check if this specific test references the method
                # (simple heuristic: look ahead in the function body)
                start = match.start()
                # Find next def or end of file
                next_def = content.find("\ndef ", start + 1)
                if next_def == -1:
                    next_def = len(content)
                body = content[start:next_def]
                if method_name in body:
                    tests.append({
                        "file": rel_path,
                        "test_name": test_name,
                        "type": test_type,
                    })

    return tests


def generate_inventory():
    """Generate the full API inventory."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_dir = os.path.join(backend_dir, "tests")

    routes = get_fastapi_routes()
    client_map = get_client_method_map()

    endpoints = []
    for route in routes:
        key = (route["method"], route["path"])
        if key in EXCLUDED_PATHS:
            continue

        # Try to match client method — normalize path params
        norm_route = normalize_path(route["path"])
        client_method = None
        for (cm, cp), mname in client_map.items():
            if cm == route["method"] and normalize_path(cp) == norm_route:
                client_method = mname
                break

        # Find tests
        tests = []
        if client_method:
            tests = find_tests_for_method(client_method, test_dir)

        has_contract = any(t["type"] == "contract" for t in tests)
        if client_method and has_contract:
            status = "fully_covered"
        elif client_method:
            status = "client_only"
        else:
            status = "missing_client"

        entry = {
            "method": route["method"],
            "path": route["path"],
            "client_method": client_method,
            "client_file": "api_client/client.py" if client_method else None,
            "tests": tests,
            "coverage_status": status,
        }
        endpoints.append(entry)

    # Summary
    total = len(endpoints) + len(EXCLUDED_ENDPOINTS)
    with_client = sum(1 for e in endpoints if e["client_method"])
    with_tests = sum(1 for e in endpoints if e["tests"])
    without_tests = sum(1 for e in endpoints if e["client_method"] and not any(t["type"] == "contract" for t in e["tests"]))

    status_counts = {}
    for e in endpoints:
        s = e["coverage_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    inventory = {
        "version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "excluded_endpoints": EXCLUDED_ENDPOINTS,
        "endpoints": endpoints,
        "summary": {
            "total_endpoints": total,
            "excluded": len(EXCLUDED_ENDPOINTS),
            "with_client_method": with_client,
            "with_tests": with_tests,
            "without_tests": without_tests,
            "coverage_status": status_counts,
        },
    }

    return inventory


def main():
    inventory = generate_inventory()

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "api_inventory.json",
    )

    with open(output_path, "w") as f:
        json.dump(inventory, f, indent=2)

    print(f"Generated {output_path}")
    print(f"  Total endpoints: {inventory['summary']['total_endpoints']}")
    print(f"  Excluded: {inventory['summary']['excluded']}")
    print(f"  With client method: {inventory['summary']['with_client_method']}")
    print(f"  With tests: {inventory['summary']['with_tests']}")
    print(f"  Without contract tests: {inventory['summary']['without_tests']}")
    print(f"  Coverage: {inventory['summary']['coverage_status']}")


if __name__ == "__main__":
    main()
