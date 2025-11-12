#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking New England Surf SC team configuration:\n")

# Get full team details
team = db_conn.client.table('teams').select('''
    id,
    name,
    league_id,
    division_id,
    leagues(id, name),
    divisions(id, name, league_id, leagues(name))
''').eq('id', 136).execute()

if team.data:
    t = team.data[0]
    print(f"Team: {t['name']} (ID {t['id']})")
    print(f"Team's league_id: {t.get('league_id', 'NULL')}")
    print(f"Team's division_id: {t.get('division_id', 'NULL')}")
    
    if t.get('leagues'):
        print(f"Team's league: {t['leagues']['name']} (ID {t['leagues']['id']})")
    
    if t.get('divisions'):
        div = t['divisions']
        league = div.get('leagues', {})
        print(f"Team's division: {div['name']} (ID {div['id']})")
        print(f"Division's league: {league.get('name', 'N/A')} (ID {div.get('league_id', 'N/A')})")
    
    # Check team_mappings for age group divisions
    print("\n\nTeam age group divisions (from team_mappings):")
    mappings = db_conn.client.table('team_mappings').select('''
        team_id,
        age_group_id,
        division_id,
        age_groups(id, name),
        divisions(id, name, league_id, leagues(name))
    ''').eq('team_id', 136).execute()
    
    for mapping in mappings.data:
        ag = mapping.get('age_groups', {})
        div = mapping.get('divisions', {})
        league = div.get('leagues', {}) if div else {}
        print(f"  Age Group: {ag.get('name', 'N/A')} - Division: {div.get('name', 'N/A')} (League: {league.get('name', 'N/A')})")

