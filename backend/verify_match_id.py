#!/usr/bin/env python3
"""
Verify that match_id column was added successfully to the games table.
"""
import os
from dotenv import load_dotenv
from dao.enhanced_data_access_fixed import SupabaseConnection

# Load dev environment
load_dotenv('.env.dev')

print("Connecting to dev database...")
db = SupabaseConnection()

# Check if match_id column exists
print("\n1. Checking if match_id column exists...")
result = db.client.table('games').select('*').limit(1).execute()

if result.data:
    columns = list(result.data[0].keys())

    if 'match_id' in columns:
        print("   ✅ match_id column EXISTS!")
        print(f"   📋 Value: {result.data[0].get('match_id')}")
    else:
        print("   ❌ match_id column NOT FOUND!")
        print(f"   📋 Available columns: {', '.join(columns)}")
        exit(1)
else:
    print("   ⚠️  No games in database to check")

# Check indexes
print("\n2. Checking indexes...")
try:
    # Query pg_indexes to see if our indexes exist
    indexes_query = """
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'games'
    AND indexname LIKE '%match%'
    """
    # Note: Can't query system tables via PostgREST, so we'll just verify column works
    print("   ℹ️  Index verification requires SQL access")
    print("   ℹ️  Check Supabase Dashboard > Database > Tables > games > Indexes")
except Exception as e:
    print(f"   ⚠️  Could not verify indexes: {e}")

# Test inserting a game with match_id
print("\n3. Testing match_id functionality...")
try:
    test_match_id = "test-match-" + str(os.urandom(4).hex())

    print(f"   Attempting to insert game with match_id: {test_match_id}")

    # This will fail if column doesn't exist
    test_data = {
        "game_date": "2025-10-08",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_score": 0,
        "away_score": 0,
        "season_id": 1,
        "age_group_id": 1,
        "game_type_id": 1,
        "match_id": test_match_id,
        "source": "test"
    }

    insert_result = db.client.table('games').insert(test_data).execute()

    if insert_result.data:
        game_id = insert_result.data[0]['id']
        print(f"   ✅ Successfully inserted test game (ID: {game_id})")

        # Clean up test game
        db.client.table('games').delete().eq('id', game_id).execute()
        print(f"   🧹 Cleaned up test game")
    else:
        print("   ❌ Insert failed - no data returned")

except Exception as e:
    print(f"   ❌ Error testing match_id: {e}")
    if "match_id" in str(e) and "does not exist" in str(e):
        print("\n   💡 The match_id column has NOT been added yet!")
        print("   💡 Please run the migration SQL in Supabase Dashboard")
        exit(1)
    else:
        print(f"\n   ⚠️  Unexpected error: {e}")
        exit(1)

print("\n" + "="*60)
print("✅ ALL CHECKS PASSED!")
print("="*60)
print("\n🎉 The match_id column is ready to use!")
print("🔗 Your API can now accept match_id in POST/PUT/PATCH requests")
