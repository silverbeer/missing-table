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
    response = supabase.auth.admin.list_users()
    users = response if isinstance(response, list) else []

    if not users:
        print("No users found in auth.users\n")
    else:
        print(f"Found {len(users)} user(s):\n")
        for user in users:
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Created: {user.created_at}")
            print(f"  Metadata: {user.user_metadata if hasattr(user, 'user_metadata') else 'N/A'}")
            print("  " + "-" * 60)

except Exception as e:
    print(f"❌ Error listing users: {e}")

print("\n💡 Next steps:")
print("1. Apply migration: https://supabase.com/dashboard/project/ppgxasqgqbnauvxozmjw/sql")
print("2. Copy/paste: supabase/migrations/20241009000017_add_username_auth.sql")
print("3. Run the migration SQL")
