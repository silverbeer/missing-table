"""
List users from auth.users via Supabase Admin API.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Load dev environment
env = os.getenv('APP_ENV', 'dev')
env_file = f'.env.{env}'
print(f"📁 Loading: {env_file}\n")
load_dotenv(env_file)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

print(f"🔗 Connecting to: {url}\n")
supabase = create_client(url, key)

print("👥 Listing users via Admin API...\n")
try:
    # Get auth users
    response = supabase.auth.admin.list_users()
    users = response if isinstance(response, list) else []

    if not users:
        print("No users found in auth.users\n")
    else:
        print(f"Found {len(users)} user(s):\n")

        # Get user profiles with usernames
        profiles_response = supabase.table('user_profiles').select('*').execute()
        profiles = {p['id']: p for p in profiles_response.data} if profiles_response.data else {}

        for user in users:
            profile = profiles.get(user.id, {})
            username = profile.get('username') or user.user_metadata.get('username') if hasattr(user, 'user_metadata') else None

            print(f"  ID: {user.id}")
            print(f"  Username: {username or 'N/A'}")
            print(f"  Email (internal): {user.email}")
            print(f"  Email (real): {profile.get('email', 'N/A')}")
            print(f"  Display Name: {profile.get('display_name', 'N/A')}")
            print(f"  Role: {profile.get('role', 'N/A')}")
            print(f"  Team ID: {profile.get('team_id', 'N/A')}")
            print(f"  Created: {user.created_at}")
            print(f"  ⚠️  Password: HASHED (cannot be retrieved)")
            print("  " + "-" * 60)

except Exception as e:
    print(f"❌ Error listing users: {e}")

print("\n💡 Next steps:")
print("1. Apply migration: https://supabase.com/dashboard/project/ppgxasqgqbnauvxozmjw/sql")
print("2. Copy/paste: supabase/migrations/20241009000017_add_username_auth.sql")
print("3. Run the migration SQL")
