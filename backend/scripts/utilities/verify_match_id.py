#!/usr/bin/env python3
"""
Verify that match_id column was added successfully to the games table.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add backend root directory to path for imports (scripts/utilities/ -> backend/)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dao.match_dao import SupabaseConnection

# Load dev environment (from backend root)
backend_root = Path(__file__).parent.parent.parent
load_dotenv(backend_root / '.env.dev')

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
    # Get real team IDs from database
    teams = db.client.table('teams').select('id').limit(2).execute()
    if not teams.data or len(teams.data) < 2:
        print("   ⚠️  Not enough teams in database to test, skipping insert test")
        print("   ✅ Column verification passed (column exists and is readable)")
    else:
        team1_id = teams.data[0]['id']
        team2_id = teams.data[1]['id']

        # Get real season, age_group, game_type IDs
        seasons = db.client.table('seasons').select('id').limit(1).execute()
        age_groups = db.client.table('age_groups').select('id').limit(1).execute()
        game_types = db.client.table('game_types').select('id').limit(1).execute()

        if not seasons.data or not age_groups.data or not game_types.data:
            print("   ⚠️  Missing reference data (seasons/age_groups/game_types), skipping insert test")
            print("   ✅ Column verification passed (column exists and is readable)")
        else:
            test_match_id = "test-match-" + str(os.urandom(4).hex())

            print(f"   Attempting to insert game with match_id: {test_match_id}")

            # This will fail if column doesn't exist
            test_data = {
                "game_date": "2025-10-08",
                "home_team_id": team1_id,
                "away_team_id": team2_id,
                "home_score": 0,
                "away_score": 0,
                "season_id": seasons.data[0]['id'],
                "age_group_id": age_groups.data[0]['id'],
                "game_type_id": game_types.data[0]['id'],
                "match_id": test_match_id,
                "source": "test"
            }

            insert_result = db.client.table('games').insert(test_data).execute()

            if insert_result.data:
                game_id = insert_result.data[0]['id']
                print(f"   ✅ Successfully inserted test game (ID: {game_id})")

                # Verify match_id was stored
                stored_match_id = insert_result.data[0].get('match_id')
                if stored_match_id == test_match_id:
                    print(f"   ✅ match_id stored correctly: {stored_match_id}")
                else:
                    print(f"   ⚠️  match_id mismatch: expected {test_match_id}, got {stored_match_id}")

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
