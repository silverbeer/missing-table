#!/usr/bin/env python3
"""Simple check of audit trail columns."""

from supabase import create_client

# Use local Supabase
SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"

client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=== Checking Migration 014 ===\n")

# Try to select from games with new columns
try:
    result = client.table("games").select("id, created_by, updated_by, source").limit(1).execute()
    print("✅ Migration successful! New columns exist:")
    print(f"   Columns: created_by, updated_by, source")
    if result.data:
        game = result.data[0]
        print(f"\n   Sample game:")
        print(f"   - ID: {game.get('id')}")
        print(f"   - Source: {game.get('source')}")
        print(f"   - Created by: {game.get('created_by')}")
        print(f"   - Updated by: {game.get('updated_by')}")
    else:
        print("   No games in database yet")
except Exception as e:
    print(f"❌ Migration may have failed:")
    print(f"   Error: {e}")

# Check if auth.users table is accessible
try:
    # Try to query auth schema - this should work with service_role key
    result = client.from_("auth.users").select("id, email").eq("email", "match-scraper@service.missingtable.com").limit(1).execute()
    if result.data:
        print(f"\n✅ Service account found in auth.users:")
        print(f"   Email: {result.data[0]['email']}")
        print(f"   ID: {result.data[0]['id']}")
    else:
        print("\n⚠️  Service account not found in auth.users")
except Exception as e:
    print(f"\n⚠️  Cannot query auth.users directly (expected): {str(e)[:100]}")
    print("   This is normal - will check user_profiles instead")

# Check user_profiles for service account
try:
    result = client.table("user_profiles").select("*").eq("role", "service_account").execute()
    if result.data:
        print(f"\n✅ Service account found in user_profiles:")
        for user in result.data:
            print(f"   Display Name: {user.get('display_name')}")
            print(f"   Role: {user.get('role')}")
            print(f"   ID: {user.get('id')}")
    else:
        print("\n⚠️  No service account in user_profiles yet")
except Exception as e:
    print(f"\n❌ Error checking user_profiles: {e}")

print("\n=== Check Complete ===")
