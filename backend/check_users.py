"""
Check users in the database to debug migration.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment based on APP_ENV
env = os.getenv('APP_ENV', 'local')
env_file = f'.env.{env}' if env != 'local' else '.env.local'
print(f"📁 Loading environment: {env} from {env_file}\n")
load_dotenv(env_file)

def check_users():
    """Check what users exist in the database."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return

    supabase = create_client(url, key)

    print(f"🔗 Connected to: {url}\n")

    # Check if user_profiles table has username column
    try:
        print("📊 Checking user_profiles structure...")
        # Try to select username column
        test_response = supabase.table('user_profiles').select('id, email, username, display_name, role').limit(1).execute()
        print("✅ Username column exists in user_profiles\n")
    except Exception as e:
        print(f"❌ Username column might not exist: {e}\n")
        print("⚠️  You need to apply the migration first!")
        print("   Run: supabase/migrations/20241009000017_add_username_auth.sql\n")

    # Get all users
    print("👥 Users in database:")
    try:
        response = supabase.table('user_profiles').select('id, email, username, display_name, role').execute()

        if not response.data or len(response.data) == 0:
            print("   (No users found)\n")
            return

        for user in response.data:
            print(f"\n   User ID: {user.get('id')}")
            print(f"   Email: {user.get('email')}")
            print(f"   Username: {user.get('username')}")
            print(f"   Display Name: {user.get('display_name')}")
            print(f"   Role: {user.get('role')}")
            print("   " + "-" * 50)

        print(f"\n📊 Total users: {len(response.data)}")

    except Exception as e:
        print(f"❌ Error querying users: {e}")

if __name__ == "__main__":
    check_users()
