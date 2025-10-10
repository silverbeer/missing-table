"""
Migrate existing user to username-based authentication.

This script updates an existing user's email-based account to use username authentication
by:
1. Adding a username to their user_profiles record
2. Updating their auth.users email to internal format (username@missingtable.local)
3. Preserving their real email in user_profiles.email for notifications
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment based on APP_ENV
env = os.getenv('APP_ENV', 'local')
env_file = f'.env.{env}' if env != 'local' else '.env.local'
print(f"📁 Loading environment: {env} from {env_file}\n")
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

    print(f"\n🔍 Looking for user with email: {email}")

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
            print(f"❌ No user found in auth.users with email: {email}")
            return False

        print(f"✅ Found user in auth.users: {user_id}")

    except Exception as e:
        print(f"❌ Error looking up user in auth.users: {e}")
        return False

    # Get user profile
    profile_response = supabase.table('user_profiles').select('*').eq('id', user_id).execute()

    if not profile_response.data or len(profile_response.data) == 0:
        print(f"❌ No profile found for user: {user_id}")
        return False

    profile = profile_response.data[0]

    print(f"✅ Found user: {profile.get('display_name', 'Unknown')} (ID: {user_id})")
    print(f"   Current email: {profile.get('email')}")
    print(f"   Current role: {profile.get('role')}")

    # Check if username is already taken
    username_check = supabase.table('user_profiles').select('id').eq('username', new_username.lower()).execute()

    if username_check.data and len(username_check.data) > 0:
        existing_user_id = username_check.data[0]['id']
        if existing_user_id != user_id:
            print(f"❌ Username '{new_username}' is already taken by another user")
            return False
        else:
            print(f"ℹ️  User already has username '{new_username}'")

    # Convert username to internal email
    internal_email = f"{new_username.lower()}@missingtable.local"

    print(f"\n📝 Migration plan:")
    print(f"   New username: {new_username}")
    print(f"   Internal email: {internal_email}")
    print(f"   Real email preserved: {email}")

    # Confirm
    if auto_confirm:
        print("\n✅ Auto-confirming migration (--yes flag)")
    else:
        confirm = input("\n⚠️  Continue with migration? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Migration cancelled")
            return False

    try:
        # Step 1: Update user_profiles with username and preserve real email
        print("\n📊 Step 1: Updating user_profiles...")
        update_data = {
            'username': new_username.lower(),
            'email': email  # Preserve real email for notifications
        }

        supabase.table('user_profiles').update(update_data).eq('id', user_id).execute()
        print("   ✅ user_profiles updated")

        # Step 2: Update auth.users email to internal format
        print("\n🔐 Step 2: Updating auth.users email...")

        # Use admin API to update user
        supabase.auth.admin.update_user_by_id(
            user_id,
            {
                "email": internal_email,
                "user_metadata": {
                    "username": new_username.lower(),
                    "is_username_auth": True
                }
            }
        )
        print("   ✅ auth.users email updated to internal format")

        print(f"\n🎉 Migration complete!")
        print(f"\n📋 User can now login with:")
        print(f"   Username: {new_username}")
        print(f"   Password: (unchanged)")
        print(f"\n📧 Real email preserved for notifications: {email}")

        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate a user from email-based auth to username-based auth",
        epilog="Example: python migrate_user_to_username.py tdrake13@gmail.com tom --yes"
    )
    parser.add_argument('email', help='Current email address of the user')
    parser.add_argument('username', help='New username to assign')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Auto-confirm migration without prompting')

    args = parser.parse_args()

    # Validate username format
    import re
    if not re.match(r'^[a-zA-Z0-9_]{3,50}$', args.username):
        print("❌ Invalid username format")
        print("   Username must be 3-50 characters (letters, numbers, underscores only)")
        sys.exit(1)

    success = migrate_user_to_username(args.email, args.username, auto_confirm=args.yes)
    sys.exit(0 if success else 1)
