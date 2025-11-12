#!/usr/bin/env python3
"""Check division_id values in matches table."""
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()
load_dotenv('.env.local', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

# Initialize connection
db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

# Query matches with division info
query = """
    SELECT
        m.id,
        m.match_date,
        m.division_id,
        d.name as division_name,
        d.league_id,
        l.name as league_name,
        t1.name as home_team,
        t2.name as away_team
    FROM matches m
    JOIN divisions d ON m.division_id = d.id
    JOIN leagues l ON d.league_id = l.id
    JOIN teams t1 ON m.home_team_id = t1.id
    JOIN teams t2 ON m.away_team_id = t2.id
    WHERE m.season_id = 3
      AND m.age_group_id = 2
      AND m.match_status = 'completed'
    ORDER BY m.match_date DESC
    LIMIT 20
"""

print("Checking matches division_id values...\n")
print(f"{'ID':<6} {'Date':<12} {'Div ID':<8} {'Division':<25} {'League':<15} {'Home':<30} {'Away':<30}")
print("=" * 150)

try:
    result = db_conn.client.table('matches').select('''
        id,
        match_date,
        division_id,
        divisions(id, name, league_id, leagues(name)),
        home_team:teams!matches_home_team_id_fkey(name),
        away_team:teams!matches_away_team_id_fkey(name)
    ''').eq('season_id', 3).eq('age_group_id', 2).eq('match_status', 'completed').order('match_date', desc=True).limit(20).execute()

    for match in result.data:
        div = match.get('divisions', {})
        league = div.get('leagues', {}) if div else {}
        print(f"{match['id']:<6} {match['match_date']:<12} {match['division_id']:<8} {div.get('name', 'N/A'):<25} {league.get('name', 'N/A'):<15} {match['home_team']['name']:<30} {match['away_team']['name']:<30}")

    print(f"\nTotal: {len(result.data)} matches")

    # Group by division and league
    print("\n\nMatches by League:")
    by_league = {}
    for match in result.data:
        div = match.get('divisions', {})
        league = div.get('leagues', {}) if div else {}
        league_name = league.get('name', 'N/A')
        by_league[league_name] = by_league.get(league_name, 0) + 1

    for league, count in sorted(by_league.items()):
        print(f"  {league}: {count} matches")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
