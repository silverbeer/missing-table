#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking cross-league matches and their match types:\n")

# Get all matches where home and away teams have different divisions
matches = db_conn.client.table('matches').select('''
    id, match_date, division_id,
    match_types(id, name),
    home_team:teams!matches_home_team_id_fkey(id, name, division_id, divisions(name, league_id, leagues(name))),
    away_team:teams!matches_away_team_id_fkey(id, name, division_id, divisions(name, league_id, leagues(name)))
''').eq('season_id', 3).eq('age_group_id', 2).execute()

cross_league = []
for m in matches.data:
    home_div_id = m['home_team'].get('division_id')
    away_div_id = m['away_team'].get('division_id')
    
    if home_div_id and away_div_id and home_div_id != away_div_id:
        cross_league.append(m)

print(f"Found {len(cross_league)} cross-league matches\n")
print(f"{'ID':<6} {'Date':<12} {'Match Type':<15} {'Home Team':<30} {'Away Team':<30}")
print("=" * 120)

match_type_counts = {}
for m in cross_league[:30]:
    match_type = m.get('match_types', {}).get('name', 'Unknown')
    match_type_counts[match_type] = match_type_counts.get(match_type, 0) + 1
    
    print(f"{m['id']:<6} {m['match_date']:<12} {match_type:<15} {m['home_team']['name']:<30} {m['away_team']['name']:<30}")

print(f"\n\nCross-league matches by match type:")
for mt, count in sorted(match_type_counts.items()):
    print(f"  {mt}: {count} matches")

print(f"\nTotal cross-league matches: {len(cross_league)}")
