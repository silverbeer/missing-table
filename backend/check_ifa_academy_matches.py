#!/usr/bin/env python3
"""Check which IFA Academy matches count in the league table."""
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

# Get all IFA Academy (ID 123) matches with team division info
matches = db_conn.client.table('matches').select('''
    id, match_date, division_id,
    home_team:teams!matches_home_team_id_fkey(id, name, division_id, divisions(name, leagues(name))),
    away_team:teams!matches_away_team_id_fkey(id, name, division_id, divisions(name, leagues(name)))
''').or_('home_team_id.eq.123,away_team_id.eq.123').eq('season_id', 3).eq('age_group_id', 2).execute()

print(f'IFA Academy (ID 123) - Total matches: {len(matches.data)}')
print('='*100)

same_division_count = 0
cross_division_count = 0

for match in matches.data:
    home_div_id = match['home_team']['division_id']
    away_div_id = match['away_team']['division_id']
    home_div = match['home_team'].get('divisions', {})
    away_div = match['away_team'].get('divisions', {})
    home_league = home_div.get('leagues', {}).get('name') if home_div else 'N/A'
    away_league = away_div.get('leagues', {}).get('name') if away_div else 'N/A'

    # Check if both teams are in division 7
    if home_div_id == 7 and away_div_id == 7:
        same_division_count += 1
        status = '✓ COUNTS'
    else:
        cross_division_count += 1
        status = '✗ FILTERED OUT'

    print(f'{status} | Match {match["id"]}: {match["home_team"]["name"]} (Div {home_div_id}) vs {match["away_team"]["name"]} (Div {away_div_id})')
    print(f'         Leagues: {home_league} vs {away_league}')

print('='*100)
print(f'Matches that COUNT in league table (both teams in Division 7): {same_division_count}')
print(f'Matches FILTERED OUT (cross-division): {cross_division_count}')
print(f'Total matches: {len(matches.data)}')
