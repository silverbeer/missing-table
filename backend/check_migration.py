#!/usr/bin/env python3
"""Check if migration 014 ran successfully."""

from supabase import create_client

# Use local Supabase
SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"

client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Checking migration status...\n")

# Check if games table has new columns
try:
    result = client.rpc("exec_sql", {"query": """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'games' AND column_name IN ('created_by', 'updated_by', 'source')
        ORDER BY column_name
    """}).execute()
    print("Games table columns:")
    for col in result.data:
        print(f"  ✅ {col['column_name']} ({col['data_type']})")
except Exception as e:
    print(f"  ❌ Error checking columns: {e}")

# Check if service account exists
try:
    result = client.rpc("exec_sql", {"query": """
        SELECT id, email, raw_user_meta_data->>'display_name' as display_name
        FROM auth.users
        WHERE email = 'match-scraper@service.missingtable.com'
    """}).execute()

    if result.data:
        print(f"\n✅ Service account exists:")
        for user in result.data:
            print(f"  ID: {user['id']}")
            print(f"  Email: {user['email']}")
            print(f"  Name: {user['display_name']}")
    else:
        print("\n❌ No service account found")
except Exception as e:
    print(f"\n❌ Error checking service account: {e}")
