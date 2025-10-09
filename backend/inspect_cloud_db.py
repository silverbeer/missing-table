"""
Inspect cloud dev database structure.
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

# Check if user_profiles table exists
print("📊 Checking for user_profiles table...")
try:
    response = supabase.table('user_profiles').select('*').limit(0).execute()
    print("✅ user_profiles table exists\n")

    # Get column info
    print("📋 Querying table structure...")
    response = supabase.rpc('get_table_columns', {'table_name': 'user_profiles'}).execute()
    print(f"Columns: {response.data}\n")
except Exception as e:
    print(f"❌ Error: {e}\n")
    print("⚠️  user_profiles table might not exist or needs migration")

# Try to get any users
print("\n👥 Attempting to list users...")
try:
    # Try basic query
    response = supabase.rpc('get_users').execute()
    print(f"Users found: {len(response.data) if response.data else 0}")
except Exception as e:
    print(f"Cannot query via RPC: {e}")

print("\n💡 To apply migration:")
print("1. Go to: https://supabase.com/dashboard/project/ppgxasqgqbnauvxozmjw/sql")
print("2. Run: supabase/migrations/20241009000017_add_username_auth.sql")
