#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking what division IFA (123) SHOULD be in based on opponents:\n")

# Get IFA (123) matches and check opponent divisions
matches = db_conn.client.table('matches').select('''
    id, match_date,
    home_team:teams!matches_home_team_id_fkey(id, name, division_id, divisions(name, leagues(name))),
    away_team:teams!matches_away_team_id_fkey(id, name, division_id, divisions(name, leagues(name)))
''').or_('home_team_id.eq.123,away_team_id.eq.123').eq('season_id', 3).eq('age_group_id', 2).execute()

print(f"IFA (ID 123) matches - checking opponent divisions:")
print(f"{'Date':<12} {'Opponent':<35} {'Opp Div':<4} {'Opp Division':<30}")
print("=" * 90)

opponent_divisions = {}
for m in matches.data:
    if m['home_team']['id'] == 123:
        opp = m['away_team']
    else:
        opp = m['home_team']
    
    opp_div = opp.get('divisions', {})
    opp_div_name = opp_div.get('name', 'N/A') if opp_div else 'N/A'
    opp_league = opp_div.get('leagues', {}).get('name', 'N/A') if opp_div else 'N/A'
    
    div_key = f"{opp_div_name} ({opp_league})"
    opponent_divisions[div_key] = opponent_divisions.get(div_key, 0) + 1
    
    print(f"{m['match_date']:<12} {opp['name']:<35} {opp.get('division_id', 'N/A'):<4} {opp_div_name:<30}")

print("\n\nOpponent division breakdown:")
for div, count in sorted(opponent_divisions.items(), key=lambda x: x[1], reverse=True):
    print(f"  {div}: {count} matches")

print("\n\nConclusion:")
if 'New England (Academy)' in str(opponent_divisions):
    print("  ⚠️  IFA (123) is playing Academy opponents but is assigned to Homegrown division!")
    print("  → Should be in Division 7 (Academy - New England)")
    print("  → Current division: 1 (Homegrown - Northeast)")
