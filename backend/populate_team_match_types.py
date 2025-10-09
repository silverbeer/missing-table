#!/usr/bin/env python3
"""Populate team_match_types table to fix Add Match team dropdown."""

import os
from dotenv import load_dotenv
from supabase import Client, create_client

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

# Load environment
load_environment()

# Initialize Supabase client
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(url, key)

def populate_team_match_types():
    """Populate team_match_types table based on team_mappings and match_types."""

    print("🔄 Populating team_match_types table...")
    print()

    # Check current state
    try:
        current_data = supabase.table("team_match_types").select("*").execute()
        print(f"📊 Current team_match_types entries: {len(current_data.data)}")

        if len(current_data.data) > 0:
            print("✅ team_match_types table already has data!")
            print("   Clearing existing data to ensure clean population...")
            supabase.table("team_match_types").delete().neq('id', 0).execute()
            print("   Cleared existing data.")

    except Exception as e:
        print(f"❌ Error checking current data: {e}")
        return False

    # Get all team mappings
    try:
        team_mappings = supabase.table("team_mappings").select("team_id, age_group_id").execute()
        print(f"📊 Found {len(team_mappings.data)} team mappings")

        if not team_mappings.data:
            print("❌ No team mappings found! Need team_mappings data first.")
            return False

    except Exception as e:
        print(f"❌ Error getting team mappings: {e}")
        return False

    # Get all match types
    try:
        match_types = supabase.table("match_types").select("id, name").execute()
        print(f"📊 Found {len(match_types.data)} match types")

        for mt in match_types.data:
            print(f"   - {mt['name']} (ID: {mt['id']})")

    except Exception as e:
        print(f"❌ Error getting match types: {e}")
        return False

    # Create team_match_types entries for each combination
    print("🔄 Creating team_match_types entries...")

    team_match_types_data = []

    for tm in team_mappings.data:
        for mt in match_types.data:
            entry = {
                'team_id': tm['team_id'],
                'match_type_id': mt['id'],
                'age_group_id': tm['age_group_id'],
                'is_active': True
            }
            team_match_types_data.append(entry)

    print(f"📊 Will create {len(team_match_types_data)} team_match_types entries")

    # Insert in batches
    batch_size = 100
    total_inserted = 0

    try:
        for i in range(0, len(team_match_types_data), batch_size):
            batch = team_match_types_data[i:i + batch_size]
            result = supabase.table("team_match_types").insert(batch).execute()
            total_inserted += len(result.data)
            print(f"   ✅ Inserted batch {i//batch_size + 1}: {len(result.data)} entries")

        print(f"✅ Successfully created {total_inserted} team_match_types entries")

    except Exception as e:
        print(f"❌ Error inserting team_match_types: {e}")
        return False

    # Verify the fix
    print("🔍 Verifying the fix...")

    try:
        # Test the specific query that was failing
        verification_query = supabase.table("team_match_types").select("*").eq('match_type_id', 1).eq('age_group_id', 1).execute()
        print(f"✅ League + U13 combinations: {len(verification_query.data)} entries")

        if len(verification_query.data) > 0:
            print("🎉 team_match_types table is now properly populated!")
            return True
        else:
            print("⚠️ No League + U13 entries found. Something may be wrong.")
            return False

    except Exception as e:
        print(f"⚠️ Error verifying fix: {e}")
        return False

if __name__ == "__main__":
    print("⚽ Team Match Types Populator")
    print("=" * 40)

    success = populate_team_match_types()

    if success:
        print()
        print("✅ Successfully populated team_match_types table!")
        print("   The Add Match screen team dropdowns should now work properly.")
        print()
        print("🔍 Test the teams API with:")
        print("   curl 'http://127.0.0.1:8000/api/teams?match_type_id=1&age_group_id=1'")
    else:
        print()
        print("❌ Failed to populate team_match_types table. Check the errors above.")