#!/usr/bin/env python3
"""
Reset user password in Supabase cloud environment.
This script uses the admin/service role to reset a user's password.
Supports username-based authentication.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from supabase import create_client

def load_environment():
    """Load environment variables based on APP_ENV or default to dev."""
    load_dotenv()
    app_env = os.getenv('APP_ENV', 'dev')
    env_file = f".env.{app_env}"
    if os.path.exists(env_file):
        print(f"Loading environment: {app_env} from {env_file}")
        load_dotenv(env_file, override=True)
    else:
        print(f"Environment file {env_file} not found, using defaults")
        if app_env != 'local':
            print("Warning: Non-local environment requested but file not found")

def reset_password(username: str = None, email: str = None, new_password: str = None):
    """Reset a user's password using Supabase admin API.

    Args:
        username: Username to look up (preferred method)
        email: Email to look up (deprecated, for backwards compatibility)
        new_password: New password to set

    Returns:
        bool: True if successful, False otherwise
    """
    load_environment()

    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    if not supabase_url or not service_key:
        print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        return False

    if not username and not email:
        print("❌ Error: Must provide either --username or --email")
        return False

    try:
        # Create admin client with service key
        supabase = create_client(supabase_url, service_key)

        user_id = None
        user_identifier = username or email

        # Look up user by username (preferred)
        if username:
            print(f"🔍 Looking up user by username: {username}")

            # Query user_profiles table for username
            profile_response = supabase.table('user_profiles')\
                .select('id, username, email, display_name')\
                .eq('username', username.lower())\
                .execute()

            if profile_response.data and len(profile_response.data) > 0:
                profile = profile_response.data[0]
                user_id = profile['id']
                print(f"✅ Found user profile:")
                print(f"   Username: {profile.get('username')}")
                print(f"   Display Name: {profile.get('display_name')}")
                print(f"   Email: {profile.get('email', 'N/A')}")
                print(f"   User ID: {user_id}")
            else:
                print(f"❌ User with username '{username}' not found")
                return False

        # Fall back to email lookup (deprecated)
        elif email:
            print(f"🔍 Looking up user by email: {email}")
            print("⚠️  Note: Email lookup is deprecated. Please use --username instead.")

            # Find user by email using admin API
            response = supabase.auth.admin.list_users()

            user_found = None
            users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

            for user in users_list:
                if hasattr(user, 'email') and user.email == email:
                    user_found = user
                    break
                elif isinstance(user, dict) and user.get('email') == email:
                    user_found = user
                    break

            if not user_found:
                print(f"❌ User with email '{email}' not found")
                return False

            user_id = user_found.id if hasattr(user_found, 'id') else user_found.get('id')
            print(f"✅ Found user: {user_id}")

        # Reset password using admin API
        print(f"🔄 Resetting password for {user_identifier}...")

        reset_response = supabase.auth.admin.update_user_by_id(
            user_id,
            {
                "password": new_password
            }
        )

        if reset_response.user:
            print(f"✅ Password reset successful for {user_identifier}")
            print(f"👤 User ID: {reset_response.user.id}")
            print(f"🔑 New password: {new_password}")
            return True
        else:
            print(f"❌ Password reset failed")
            return False

    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Reset user password in Supabase (supports username-based authentication)',
        epilog='Examples:\n'
               '  %(prog)s --username tom --password newpass123 --confirm\n'
               '  %(prog)s --email user@example.com --password newpass123\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--username', help='Username to reset password for (preferred)')
    parser.add_argument('--email', help='User email to reset password for (deprecated)')
    parser.add_argument('--password', required=True, help='New password to set')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    # Validate that at least one identifier is provided
    if not args.username and not args.email:
        parser.error("Must provide either --username or --email")

    print(f"🔐 Password Reset Tool")
    if args.username:
        print(f"👤 Username: {args.username}")
    if args.email:
        print(f"📧 Email: {args.email}")
        if args.username:
            print("⚠️  Note: Both username and email provided. Using username (preferred).")
    print(f"🆕 New Password: {args.password}")
    print(f"🌍 Environment: {os.getenv('APP_ENV', 'dev')}")

    if not args.confirm:
        user_identifier = args.username or args.email
        confirm = input(f"\n⚠️  Are you sure you want to reset password for '{user_identifier}'? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Password reset cancelled")
            return

    success = reset_password(
        username=args.username,
        email=args.email,
        new_password=args.password
    )

    if success:
        print("\n🎉 Password reset completed successfully!")
        print(f"💡 You can now log in with:")
        if args.username:
            print(f"   Username: {args.username}")
        if args.email:
            print(f"   Email: {args.email}")
        print(f"   Password: {args.password}")
    else:
        print("\n💥 Password reset failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()