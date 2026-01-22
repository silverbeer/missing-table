"""
Migrate existing user to username-based authentication.

This script updates an existing user's email-based account to use username authentication
by:
1. Adding a username to their user_profiles record
2. Updating their auth.users email to internal format (username@missingtable.local)
3. Preserving their real email in user_profiles.email for notifications
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from supabase import Client, create_client

# Load environment based on APP_ENV
env = os.getenv("APP_ENV", "local")
env_file = f".env.{env}" if env != "local" else ".env.local"
load_dotenv(env_file)


def get_supabase_client() -> Client:
    """Get Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

    return create_client(url, key)


def migrate_user_to_username(email: str, new_username: str, auto_confirm: bool = False):
    """
    Migrate a user from email-based auth to username-based auth.

    Args:
        email: The user's current email address
        new_username: The new username to assign
        auto_confirm: If True, skip confirmation prompt
    """
    supabase = get_supabase_client()

    # First, find user in auth.users by email
    try:
        auth_users = supabase.auth.admin.list_users()
        users_list = auth_users if isinstance(auth_users, list) else []

        user_id = None
        for user in users_list:
            if user.email == email:
                user_id = user.id
                break

        if not user_id:
            return False

    except Exception:
        return False

    # Get user profile
    profile_response = supabase.table("user_profiles").select("*").eq("id", user_id).execute()

    if not profile_response.data or len(profile_response.data) == 0:
        return False

    profile_response.data[0]

    # Check if username is already taken
    username_check = supabase.table("user_profiles").select("id").eq("username", new_username.lower()).execute()

    if username_check.data and len(username_check.data) > 0:
        existing_user_id = username_check.data[0]["id"]
        if existing_user_id != user_id:
            return False
        else:
            pass

    # Convert username to internal email
    internal_email = f"{new_username.lower()}@missingtable.local"

    # Confirm
    if auto_confirm:
        pass
    else:
        confirm = input("\n⚠️  Continue with migration? (yes/no): ")
        if confirm.lower() != "yes":
            return False

    try:
        # Step 1: Update user_profiles with username and preserve real email
        update_data = {
            "username": new_username.lower(),
            "email": email,  # Preserve real email for notifications
        }

        supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()

        # Step 2: Update auth.users email to internal format

        # Use admin API to update user
        supabase.auth.admin.update_user_by_id(
            user_id,
            {
                "email": internal_email,
                "user_metadata": {"username": new_username.lower(), "is_username_auth": True},
            },
        )

        return True

    except Exception:
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate a user from email-based auth to username-based auth",
        epilog="Example: python migrate_user_to_username.py tdrake13@gmail.com tom --yes",
    )
    parser.add_argument("email", help="Current email address of the user")
    parser.add_argument("username", help="New username to assign")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm migration without prompting")

    args = parser.parse_args()

    # Validate username format
    import re

    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", args.username):
        sys.exit(1)

    success = migrate_user_to_username(args.email, args.username, auto_confirm=args.yes)
    sys.exit(0 if success else 1)
