#!/usr/bin/env python3
"""
Sync users between local and production environments.

This script ensures test users can use the same credentials in both local and prod.

Usage:
    # Sync from local to prod (creates missing users in prod)
    APP_ENV=local python sync_users.py --to prod

    # Sync from prod to local (creates missing users in local)
    APP_ENV=prod python sync_users.py --to local

    # Dry run (see what would be synced without making changes)
    APP_ENV=local python sync_users.py --to prod --dry-run

    # Set specific password for new users
    APP_ENV=local python sync_users.py --to prod --password "TestPass123!"
"""

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def load_environment(env: str) -> dict[str, str]:
    """Load environment variables for specified environment."""
    backend_path = Path(__file__).parent.parent.parent
    env_path = backend_path / f".env.{env}"

    if not env_path.exists():
        raise Exception(f"Environment file not found: {env_path}")

    load_dotenv(env_path, override=True)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise Exception(f"Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in {env_path}")

    return {"url": url, "key": key, "env": env}


def get_users(config: dict[str, str]) -> list[dict]:
    """Get all users from environment using Admin API."""
    admin_url = f"{config['url']}/auth/v1/admin/users"
    headers = {
        "apikey": config["key"],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
    }

    response = requests.get(admin_url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch users: {response.status_code} - {response.text}")

    return response.json().get("users", [])


def create_user(config: dict[str, str], email: str, password: str, user_metadata: dict) -> dict:
    """Create a new user in target environment."""
    admin_url = f"{config['url']}/auth/v1/admin/users"
    headers = {
        "apikey": config["key"],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,  # Auto-confirm email
        "user_metadata": user_metadata,
    }

    response = requests.post(admin_url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to create user {email}: {response.status_code} - {response.text}")

    return response.json()


def sync_users(source_env: str, target_env: str, password: str | None = None, dry_run: bool = False):
    """Sync users from source to target environment."""

    # Load configurations
    source_config = load_environment(source_env)

    target_config = load_environment(target_env)

    # Get users from both environments
    source_users = get_users(source_config)

    target_users = get_users(target_config)

    # Create email lookup for target users
    target_emails = {user["email"]: user for user in target_users}

    # Find users that need to be created
    users_to_create = []
    for user in source_users:
        if user["email"] not in target_emails:
            users_to_create.append(user)

    if len(users_to_create) == 0:
        return

    # Determine password strategy
    if password is None:
        password = os.getenv("SYNC_DEFAULT_PASSWORD", "ChangeMe123!")

    # Show what will be created
    for user in users_to_create:
        metadata = user.get("user_metadata", {})
        metadata.get("display_name", "Unknown")

    if dry_run:
        return

    # Confirm before proceeding
    response = input(f"Create {len(users_to_create)} users in {target_env}? (yes/no): ")
    if response.lower() != "yes":
        return

    # Create users

    created_count = 0
    failed_count = 0

    for user in users_to_create:
        email = user["email"]
        metadata = user.get("user_metadata", {})

        try:
            create_user(target_config, email, password, metadata)
            created_count += 1
        except Exception:
            failed_count += 1

    # Summary
    if failed_count > 0:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync users between environments")
    parser.add_argument(
        "--to",
        required=True,
        choices=["dev", "prod", "local"],
        help="Target environment to sync users to",
    )
    parser.add_argument("--password", default=None, help="Password for newly created users")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without making changes")

    args = parser.parse_args()

    # Source env from APP_ENV
    source_env = os.getenv("APP_ENV", "local")
    target_env = args.to

    if source_env == target_env:
        sys.exit(1)

    try:
        sync_users(source_env, target_env, args.password, args.dry_run)
    except Exception:
        sys.exit(1)
