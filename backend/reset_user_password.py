#!/usr/bin/env python3
"""
Reset user password in Supabase cloud environment.
This script uses the admin/service role to reset a user's password.
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

def reset_password(email: str, new_password: str):
    """Reset a user's password using Supabase admin API."""
    load_environment()

    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    if not supabase_url or not service_key:
        print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        return False

    try:
        # Create admin client with service key
        supabase = create_client(supabase_url, service_key)

        print(f"🔍 Looking up user: {email}")

        # Find user by email using admin API
        # Note: Supabase admin methods require service role key
        response = supabase.auth.admin.list_users()

        user_found = None

        # Handle different response structures
        users_list = response if isinstance(response, list) else getattr(response, 'data', {}).get('users', [])

        for user in users_list:
            if hasattr(user, 'email') and user.email == email:
                user_found = user
                break
            elif isinstance(user, dict) and user.get('email') == email:
                user_found = user
                break

        if not user_found:
            print(f"❌ User {email} not found")
            return False

        # Get user ID
        user_id = user_found.id if hasattr(user_found, 'id') else user_found.get('id')
        print(f"✅ Found user: {user_id}")

        # Reset password using admin API
        print(f"🔄 Resetting password for {email}...")

        reset_response = supabase.auth.admin.update_user_by_id(
            user_id,
            {
                "password": new_password
            }
        )

        if reset_response.user:
            print(f"✅ Password reset successful for {email}")
            print(f"📧 User ID: {reset_response.user.id}")
            print(f"🔑 New password: {new_password}")
            return True
        else:
            print(f"❌ Password reset failed")
            return False

    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Reset user password in Supabase')
    parser.add_argument('--email', required=True, help='User email to reset password for')
    parser.add_argument('--password', required=True, help='New password to set')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')

    args = parser.parse_args()

    print(f"🔐 Password Reset Tool")
    print(f"📧 Email: {args.email}")
    print(f"🆕 New Password: {args.password}")
    print(f"🌍 Environment: {os.getenv('APP_ENV', 'dev')}")

    if not args.confirm:
        confirm = input("\n⚠️  Are you sure you want to reset this password? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Password reset cancelled")
            return

    success = reset_password(args.email, args.password)

    if success:
        print("\n🎉 Password reset completed successfully!")
        print(f"💡 You can now log in with:")
        print(f"   Email: {args.email}")
        print(f"   Password: {args.password}")
    else:
        print("\n💥 Password reset failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()