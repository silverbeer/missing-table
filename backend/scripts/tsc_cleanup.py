#!/usr/bin/env python3
"""
TSC Test Data Cleanup Script

Safely cleans up TSC test data by querying entities by name prefix.
Works on any environment (local, prod) without needing a registry file.

Usage:
    # Clean up tsc_a_ data from production
    BASE_URL=https://missingtable.com uv run python scripts/tsc_cleanup.py --prefix tsc_a_

    # Clean up tsc_b_ data from local
    uv run python scripts/tsc_cleanup.py --prefix tsc_b_

    # Dry run (show what would be deleted without deleting)
    BASE_URL=https://missingtable.com uv run python scripts/tsc_cleanup.py --prefix tsc_a_ --dry-run
"""

import argparse
import os
import sys
from pathlib import Path

import httpx


# Load .env.tsc file if it exists
def load_env_file():
    """Load environment variables from .env.tsc file."""
    env_files = [
        # Check multiple common locations
        Path(__file__).parent.parent / ".env.tsc",  # backend/.env.tsc
        Path(__file__).parent.parent / "tests" / ".env.tsc",  # backend/tests/.env.tsc
        Path(__file__).parent.parent / "tests" / "tsc" / ".env.tsc",  # backend/tests/tsc/.env.tsc
        Path.cwd() / ".env.tsc",
        Path.cwd() / "tests" / ".env.tsc",
        Path.cwd() / "tests" / "tsc" / ".env.tsc",
    ]

    for env_file in env_files:
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Don't override existing env vars
                        if key not in os.environ:
                            os.environ[key] = value
            return True
    return False


load_env_file()


def create_client(base_url: str) -> httpx.Client:
    """Create an HTTP client with timeout."""
    return httpx.Client(base_url=base_url, timeout=30)


def login(client: httpx.Client, username: str, password: str) -> dict:
    """Login and return headers with auth token."""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})

    if resp.status_code != 200:
        sys.exit(1)

    token = resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def find_entities(client: httpx.Client, headers: dict, endpoint: str, prefix: str, name_field: str = "name") -> list:
    """Find entities matching the prefix."""
    resp = client.get(endpoint, headers=headers)
    if resp.status_code != 200:
        return []

    entities = resp.json()
    if isinstance(entities, dict):
        # Some endpoints return {"data": [...]} or similar
        entities = entities.get("data", entities.get("items", []))

    return [e for e in entities if e.get(name_field, "").startswith(prefix)]


def delete_entity(client: httpx.Client, headers: dict, endpoint: str, entity_id: int, name: str, dry_run: bool) -> bool:
    """Delete a single entity."""
    if dry_run:
        return True

    resp = client.delete(f"{endpoint}/{entity_id}", headers=headers)
    return resp.status_code in (200, 204)


def find_matches_by_teams(client: httpx.Client, headers: dict, team_ids: list[int]) -> list:
    """Find matches involving any of the given teams."""
    if not team_ids:
        return []

    resp = client.get("/api/matches", headers=headers)
    if resp.status_code != 200:
        return []

    matches = resp.json()
    if isinstance(matches, dict):
        matches = matches.get("data", matches.get("items", matches.get("matches", [])))

    return [m for m in matches if m.get("home_team_id") in team_ids or m.get("away_team_id") in team_ids]


def cleanup(base_url: str, username: str, password: str, prefix: str, dry_run: bool):
    """Main cleanup function."""

    client = create_client(base_url)
    headers = login(client, username, password)

    # Track what we find
    summary = {}

    # Step 1: Find teams first (needed to find matches)
    teams = find_entities(client, headers, "/api/teams", prefix)
    summary["teams"] = len(teams)
    team_ids = [t["id"] for t in teams]
    for _t in teams:
        pass

    # Step 2: Find and delete matches involving these teams
    matches = find_matches_by_teams(client, headers, team_ids)
    summary["matches"] = len(matches)
    for m in matches:
        match_name = f"Match {m['id']}: {m.get('home_team_id')} vs {m.get('away_team_id')}"
        delete_entity(client, headers, "/api/matches", m["id"], match_name, dry_run)

    # Step 3: Delete teams
    for t in teams:
        delete_entity(client, headers, "/api/teams", t["id"], t["name"], dry_run)

    # Step 4: Find and delete clubs
    clubs = find_entities(client, headers, "/api/clubs?include_teams=false", prefix)
    summary["clubs"] = len(clubs)
    for c in clubs:
        delete_entity(client, headers, "/api/clubs", c["id"], c["name"], dry_run)

    # Step 5: Find and delete divisions
    divisions = find_entities(client, headers, "/api/divisions", prefix)
    summary["divisions"] = len(divisions)
    for d in divisions:
        delete_entity(client, headers, "/api/divisions", d["id"], d["name"], dry_run)

    # Step 6: Find and delete leagues
    leagues = find_entities(client, headers, "/api/leagues", prefix)
    summary["leagues"] = len(leagues)
    for lg in leagues:
        delete_entity(client, headers, "/api/leagues", lg["id"], lg["name"], dry_run)

    # Step 7: Find and delete age groups
    age_groups = find_entities(client, headers, "/api/age-groups", prefix)
    summary["age_groups"] = len(age_groups)
    for ag in age_groups:
        delete_entity(client, headers, "/api/age-groups", ag["id"], ag["name"], dry_run)

    # Step 8: Find and delete seasons
    seasons = find_entities(client, headers, "/api/seasons", prefix)
    summary["seasons"] = len(seasons)
    for s in seasons:
        delete_entity(client, headers, "/api/seasons", s["id"], s["name"], dry_run)

    # Summary

    total = sum(summary.values())

    if dry_run and total > 0:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Clean up TSC test data by name prefix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run against production (see what would be deleted)
    BASE_URL=https://missingtable.com uv run python scripts/tsc_cleanup.py --prefix tsc_a_ --dry-run

    # Actually delete from production
    BASE_URL=https://missingtable.com uv run python scripts/tsc_cleanup.py --prefix tsc_a_

    # Clean up local environment
    uv run python scripts/tsc_cleanup.py --prefix tsc_a_
        """,
    )

    parser.add_argument("--prefix", required=True, help="Entity name prefix to clean up (e.g., tsc_a_ or tsc_b_)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("TSC_EXISTING_ADMIN_USERNAME", "tom"),
        help="Admin username (default: from TSC_EXISTING_ADMIN_USERNAME or 'tom')",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("TSC_EXISTING_ADMIN_PASSWORD"),
        help="Admin password (default: from TSC_EXISTING_ADMIN_PASSWORD)",
    )

    args = parser.parse_args()

    base_url = os.getenv("BASE_URL", "http://localhost:8000")

    # If no password provided, try common patterns
    password = args.password
    if not password:
        password = f"{args.username}123!"

    cleanup(base_url, args.username, password, args.prefix, args.dry_run)


if __name__ == "__main__":
    main()
