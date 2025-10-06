#!/usr/bin/env python3
"""
OpenAPI Coverage Gap Analyzer.

Compares pytest test coverage against OpenAPI schema to identify untested endpoints.

Usage:
    uv run python scripts/check_api_coverage.py
    uv run python scripts/check_api_coverage.py --format json
    uv run python scripts/check_api_coverage.py --threshold 85
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer()
console = Console()


def load_openapi_schema(schema_path: Path) -> dict[str, Any]:
    """Load OpenAPI schema from file."""
    with open(schema_path) as f:
        return json.load(f)


def extract_endpoints_from_schema(schema: dict[str, Any]) -> dict[str, list[str]]:
    """Extract all endpoints and their methods from OpenAPI schema."""
    endpoints = defaultdict(list)

    for path, methods in schema.get("paths", {}).items():
        for method in methods.keys():
            if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                endpoints[path].append(method.upper())

    return dict(endpoints)


def find_test_files() -> list[Path]:
    """Find all test files in the tests directory."""
    test_dir = Path(__file__).parent.parent / "tests"
    return list(test_dir.rglob("test_*.py"))


def extract_tested_endpoints(test_files: list[Path]) -> dict[str, set[str]]:
    """Extract endpoints tested from test files."""
    tested = defaultdict(set)

    for test_file in test_files:
        content = test_file.read_text()

        # Look for API calls in test files
        # Patterns to match:
        # - client.get("/api/...")
        # - api_client.post("/api/...")
        # - _request("GET", "/api/...")
        # - test_client.get("/api/...")

        import re

        # Pattern for method calls
        patterns = [
            r'\.get\(["\']([^"\']+)["\']',  # .get("/api/...")
            r'\.post\(["\']([^"\']+)["\']',  # .post("/api/...")
            r'\.put\(["\']([^"\']+)["\']',  # .put("/api/...")
            r'\.patch\(["\']([^"\']+)["\']',  # .patch("/api/...")
            r'\.delete\(["\']([^"\']+)["\']',  # .delete("/api/...")
            r'_request\(["\'](\w+)["\'],\s*["\']([^"\']+)["\']',  # _request("GET", "/api/...")
        ]

        for line in content.split("\n"):
            for pattern in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    if "_request" in pattern:
                        method = match.group(1).upper()
                        path = match.group(2)
                    else:
                        method = pattern.split("\\")[1].split("(")[0].upper()
                        path = match.group(1)

                    # Normalize path (remove query params, replace path params)
                    path = path.split("?")[0]

                    # Convert specific IDs to path parameters
                    # /api/teams/1 -> /api/teams/{team_id}
                    path = re.sub(r'/\d+', '/{id}', path)

                    # Try to match with actual schema paths
                    if path.startswith("/api") or path.startswith("/health"):
                        tested[path].add(method)

    return dict(tested)


def normalize_path_for_matching(path: str) -> str:
    """Normalize path for fuzzy matching with schema."""
    # Remove trailing slashes
    path = path.rstrip("/")

    # Handle common path parameter patterns
    path = re.sub(r'/\{[^}]+\}', '/{id}', path)

    return path


def match_tested_to_schema(
    schema_endpoints: dict[str, list[str]], tested_endpoints: dict[str, set[str]]
) -> dict[str, dict[str, Any]]:
    """Match tested endpoints to schema endpoints."""
    import re

    coverage = {}

    for schema_path, schema_methods in schema_endpoints.items():
        coverage[schema_path] = {
            "methods": schema_methods,
            "tested_methods": [],
            "untested_methods": [],
        }

        # Try exact match first
        if schema_path in tested_endpoints:
            tested_methods = tested_endpoints[schema_path]
            coverage[schema_path]["tested_methods"] = [
                m for m in schema_methods if m in tested_methods
            ]
        else:
            # Try fuzzy matching
            normalized_schema = normalize_path_for_matching(schema_path)

            for tested_path, tested_methods in tested_endpoints.items():
                normalized_tested = normalize_path_for_matching(tested_path)

                # Check if paths match (accounting for path parameters)
                if normalized_schema == normalized_tested or schema_path == tested_path:
                    coverage[schema_path]["tested_methods"] = [
                        m for m in schema_methods if m in tested_methods
                    ]
                    break

        coverage[schema_path]["untested_methods"] = [
            m
            for m in schema_methods
            if m not in coverage[schema_path]["tested_methods"]
        ]

    return coverage


def calculate_coverage_stats(coverage: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Calculate coverage statistics."""
    total_endpoints = 0
    tested_endpoints = 0
    total_methods = 0
    tested_methods = 0

    category_stats = defaultdict(lambda: {"total": 0, "tested": 0})

    for path, data in coverage.items():
        # Categorize by first path segment
        category = path.split("/")[2] if len(path.split("/")) > 2 else "other"

        total_methods += len(data["methods"])
        tested_methods += len(data["tested_methods"])

        category_stats[category]["total"] += len(data["methods"])
        category_stats[category]["tested"] += len(data["tested_methods"])

        if data["tested_methods"]:
            tested_endpoints += 1
        total_endpoints += 1

    endpoint_coverage = (tested_endpoints / total_endpoints * 100) if total_endpoints > 0 else 0
    method_coverage = (tested_methods / total_methods * 100) if total_methods > 0 else 0

    return {
        "total_endpoints": total_endpoints,
        "tested_endpoints": tested_endpoints,
        "total_methods": total_methods,
        "tested_methods": tested_methods,
        "endpoint_coverage_pct": endpoint_coverage,
        "method_coverage_pct": method_coverage,
        "category_stats": dict(category_stats),
    }


def print_coverage_report(coverage: dict[str, dict[str, Any]], stats: dict[str, Any]) -> None:
    """Print coverage report using rich."""
    console.print("\n")
    console.print(
        Panel.fit(
            f"[bold cyan]API Contract Coverage Report[/bold cyan]",
            border_style="cyan",
        )
    )

    # Overall stats
    console.print(f"\n[bold]Overall Coverage:[/bold]")
    console.print(
        f"  Endpoints: {stats['tested_endpoints']}/{stats['total_endpoints']} "
        f"([{'green' if stats['endpoint_coverage_pct'] >= 80 else 'yellow' if stats['endpoint_coverage_pct'] >= 60 else 'red'}]{stats['endpoint_coverage_pct']:.1f}%[/])"
    )
    console.print(
        f"  Methods: {stats['tested_methods']}/{stats['total_methods']} "
        f"([{'green' if stats['method_coverage_pct'] >= 80 else 'yellow' if stats['method_coverage_pct'] >= 60 else 'red'}]{stats['method_coverage_pct']:.1f}%[/])"
    )

    # Category breakdown
    console.print(f"\n[bold]Coverage by Category:[/bold]")
    for category, cat_stats in sorted(stats["category_stats"].items()):
        pct = (cat_stats["tested"] / cat_stats["total"] * 100) if cat_stats["total"] > 0 else 0
        status = "✅" if pct == 100 else "⚠️" if pct >= 50 else "❌"
        color = "green" if pct >= 80 else "yellow" if pct >= 60 else "red"
        console.print(
            f"  {status} {category}: {cat_stats['tested']}/{cat_stats['total']} ([{color}]{pct:.0f}%[/])"
        )

    # Detailed endpoint table
    table = Table(title="\nEndpoint Coverage Details")
    table.add_column("Path", style="cyan")
    table.add_column("Methods", style="blue")
    table.add_column("Tested", style="green")
    table.add_column("Untested", style="red")
    table.add_column("Status", justify="center")

    for path in sorted(coverage.keys()):
        data = coverage[path]
        methods_str = ", ".join(data["methods"])
        tested_str = ", ".join(data["tested_methods"]) if data["tested_methods"] else "-"
        untested_str = ", ".join(data["untested_methods"]) if data["untested_methods"] else "-"

        if not data["untested_methods"]:
            status = "✅"
        elif data["tested_methods"]:
            status = "⚠️"
        else:
            status = "❌"

        table.add_row(path, methods_str, tested_str, untested_str, status)

    console.print(table)


@app.command()
def main(
    schema_path: Path = typer.Option(
        Path(__file__).parent.parent / "openapi.json",
        "--schema",
        "-s",
        help="Path to OpenAPI schema file",
    ),
    format: str = typer.Option("rich", "--format", "-f", help="Output format: rich, json, or text"),
    threshold: int = typer.Option(
        80, "--threshold", "-t", help="Minimum coverage threshold (0-100)"
    ),
    fail_below: bool = typer.Option(
        False, "--fail-below", help="Exit with error code if below threshold"
    ),
) -> None:
    """Check API test coverage against OpenAPI schema."""
    # Load schema
    schema = load_openapi_schema(schema_path)
    schema_endpoints = extract_endpoints_from_schema(schema)

    # Find test files
    test_files = find_test_files()
    tested_endpoints = extract_tested_endpoints(test_files)

    # Match and calculate coverage
    coverage = match_tested_to_schema(schema_endpoints, tested_endpoints)
    stats = calculate_coverage_stats(coverage)

    # Output results
    if format == "json":
        output = {
            "coverage": coverage,
            "stats": stats,
        }
        console.print_json(data=output)
    elif format == "rich":
        print_coverage_report(coverage, stats)
    else:  # text
        console.print(f"Coverage: {stats['method_coverage_pct']:.1f}%")
        console.print(f"Tested: {stats['tested_methods']}/{stats['total_methods']} methods")

    # Check threshold
    if fail_below and stats["method_coverage_pct"] < threshold:
        console.print(
            f"\n[red]❌ Coverage {stats['method_coverage_pct']:.1f}% is below threshold {threshold}%[/red]"
        )
        sys.exit(1)

    console.print(f"\n[green]✅ Coverage check complete![/green]")


if __name__ == "__main__":
    app()
