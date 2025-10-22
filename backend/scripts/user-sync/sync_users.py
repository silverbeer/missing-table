#!/usr/bin/env python3
"""
Sync users between dev and production environments.

This script ensures test users can use the same credentials in both dev and prod.

Usage:
    # Sync from dev to prod (creates missing users in prod)
    APP_ENV=dev python sync_users.py --to prod

    # Sync from prod to dev (creates missing users in dev)
    APP_ENV=prod python sync_users.py --to dev

    # Dry run (see what would be synced without making changes)
    APP_ENV=dev python sync_users.py --to prod --dry-run

    # Set specific password for new users
    APP_ENV=dev python sync_users.py --to prod --password "TestPass123!"
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
from typing import Dict, List
import json

def load_environment(env: str) -> Dict[str, str]:
    """Load environment variables for specified environment."""
    backend_path = Path(__file__).parent.parent.parent
    env_path = backend_path / f'.env.{env}'

    if not env_path.exists():
        raise Exception(f"Environment file not found: {env_path}")

    load_dotenv(env_path, override=True)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise Exception(f"Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in {env_path}")

    return {
        'url': url,
        'key': key,
        'env': env
    }

def get_users(config: Dict[str, str]) -> List[Dict]:
    """Get all users from environment using Admin API."""
    admin_url = f"{config['url']}/auth/v1/admin/users"
    headers = {
        "apikey": config['key'],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json"
    }

    response = requests.get(admin_url, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch users: {response.status_code} - {response.text}")

    return response.json().get('users', [])

def create_user(config: Dict[str, str], email: str, password: str, user_metadata: Dict) -> Dict:
    """Create a new user in target environment."""
    admin_url = f"{config['url']}/auth/v1/admin/users"
    headers = {
        "apikey": config['key'],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,  # Auto-confirm email
        "user_metadata": user_metadata
    }

    response = requests.post(admin_url, headers=headers, json=payload)

    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to create user {email}: {response.status_code} - {response.text}")

    return response.json()

def sync_users(source_env: str, target_env: str, password: str = None, dry_run: bool = False):
    """Sync users from source to target environment."""
    print(f"\n{'='*80}")
    print(f"User Sync: {source_env} → {target_env}")
    print(f"{'='*80}\n")

    # Load configurations
    print(f"📡 Loading {source_env} environment...")
    source_config = load_environment(source_env)

    print(f"📡 Loading {target_env} environment...")
    target_config = load_environment(target_env)

    # Get users from both environments
    print(f"\n🔍 Fetching users from {source_env}...")
    source_users = get_users(source_config)
    print(f"   Found {len(source_users)} users")

    print(f"\n🔍 Fetching users from {target_env}...")
    target_users = get_users(target_config)
    print(f"   Found {len(target_users)} users")

    # Create email lookup for target users
    target_emails = {user['email']: user for user in target_users}

    # Find users that need to be created
    users_to_create = []
    for user in source_users:
        if user['email'] not in target_emails:
            users_to_create.append(user)

    print(f"\n{'='*80}")
    print(f"Sync Summary")
    print(f"{'='*80}")
    print(f"Users in {source_env}: {len(source_users)}")
    print(f"Users in {target_env}: {len(target_users)}")
    print(f"Users to create in {target_env}: {len(users_to_create)}")

    if len(users_to_create) == 0:
        print("\n✅ All users already exist in target environment!")
        return

    # Determine password strategy
    if password is None:
        password = os.getenv('SYNC_DEFAULT_PASSWORD', 'ChangeMe123!')
        print(f"\n⚠️  Using default password: {password}")
        print("   Set SYNC_DEFAULT_PASSWORD env var or use --password flag to change")

    # Show what will be created
    print(f"\n{'='*80}")
    print("Users to create:")
    print(f"{'='*80}")
    for user in users_to_create:
        metadata = user.get('user_metadata', {})
        display_name = metadata.get('display_name', 'Unknown')
        print(f"  📧 {user['email']}")
        print(f"     Name: {display_name}")
        print(f"     Role: {user.get('role', 'N/A')}")

    if dry_run:
        print(f"\n🏷️  DRY RUN - No changes made")
        return

    # Confirm before proceeding
    print(f"\n{'='*80}")
    response = input(f"Create {len(users_to_create)} users in {target_env}? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return

    # Create users
    print(f"\n{'='*80}")
    print("Creating users...")
    print(f"{'='*80}")

    created_count = 0
    failed_count = 0

    for user in users_to_create:
        email = user['email']
        metadata = user.get('user_metadata', {})

        try:
            print(f"\n📝 Creating {email}...")
            new_user = create_user(target_config, email, password, metadata)
            print(f"   ✅ Created with ID: {new_user['id']}")
            created_count += 1
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            failed_count += 1

    # Summary
    print(f"\n{'='*80}")
    print("Sync Complete")
    print(f"{'='*80}")
    print(f"✅ Created: {created_count}")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")

    print(f"\n📋 Next steps:")
    print(f"1. Test users can now log in to {target_env} with:")
    print(f"   Email: <their email>")
    print(f"   Password: {password}")
    print(f"2. Users should change their password after first login")
    print(f"3. Or send password reset emails via Supabase Dashboard")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync users between environments")
    parser.add_argument('--to', required=True, choices=['dev', 'prod', 'local'],
                       help='Target environment to sync users to')
    parser.add_argument('--password', default=None,
                       help='Password for newly created users')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be synced without making changes')

    args = parser.parse_args()

    # Source env from APP_ENV
    source_env = os.getenv('APP_ENV', 'dev')
    target_env = args.to

    if source_env == target_env:
        print(f"❌ Source and target environment are the same: {source_env}")
        print(f"   Set APP_ENV to source environment, and use --to for target")
        sys.exit(1)

    try:
        sync_users(source_env, target_env, args.password, args.dry_run)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
