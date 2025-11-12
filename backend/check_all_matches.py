#!/usr/bin/env python3
"""Check what matches exist in database."""
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()
load_dotenv('.env.local', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

# Initialize connection
db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

print("Checking what matches exist...\n")

try:
    # First, check seasons
    seasons = db_conn.client.table('seasons').select('*').execute()
    print("Seasons in database:")
    for s in seasons.data:
        print(f"  {s['id']}: {s['name']}")

    print("\nAge Groups in database:")
    age_groups = db_conn.client.table('age_groups').select('*').execute()
    for ag in age_groups.data:
        print(f"  {ag['id']}: {ag['name']}")

    print("\nDivisions in database:")
    divisions = db_conn.client.table('divisions').select('*, leagues(name)').execute()
    for d in divisions.data:
        print(f"  {d['id']}: {d['name']} (League: {d.get('leagues', {}).get('name', 'N/A')})")

    print("\nAll matches (last 20):")
    result = db_conn.client.table('matches').select('''
        id,
        match_date,
        match_status,
        season_id,
        age_group_id,
        division_id,
        home_score,
        away_score,
        home_team:teams!matches_home_team_id_fkey(name),
        away_team:teams!matches_away_team_id_fkey(name)
    ''').order('id', desc=True).limit(20).execute()

    print(f"{'ID':<6} {'Season':<8} {'Age':<6} {'Div':<6} {'Status':<12} {'Score':<8} {'Home':<25} {'Away':<25}")
    print("=" * 130)

    for match in result.data:
        status = match.get('match_status', 'NULL')
        score = f"{match.get('home_score', '-')}-{match.get('away_score', '-')}"
        print(f"{match['id']:<6} {match['season_id']:<8} {match['age_group_id']:<6} {match['division_id']:<6} {str(status):<12} {score:<8} {match['home_team']['name']:<25} {match['away_team']['name']:<25}")

    print(f"\nTotal matches in database: {len(result.data)}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
