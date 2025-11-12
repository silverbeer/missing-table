#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking NEFC team configuration and matches:\n")

# Get NEFC team
nefc = db_conn.client.table('teams').select('''
    id, name, league_id, division_id,
    leagues(name), divisions(name, leagues(name))
''').ilike('name', '%NEFC%').execute()

print("NEFC teams found:")
for team in nefc.data:
    league = team.get('leagues', {})
    division = team.get('divisions', {})
    div_league = division.get('leagues', {}) if division else {}
    print(f"  ID {team['id']}: {team['name']}")
    print(f"    League: {league.get('name', 'N/A')} (ID {team.get('league_id', 'NULL')})")
    print(f"    Division: {division.get('name', 'N/A')} (ID {team.get('division_id', 'NULL')}, League: {div_league.get('name', 'N/A')})")

# Get NEFC matches for U14 in 2025-2026
nefc_id = nefc.data[0]['id'] if nefc.data else None
if nefc_id:
    print(f"\n\nNEFC (ID {nefc_id}) U14 matches showing cross-league games:")
    matches = db_conn.client.table('matches').select('''
        id, match_date, division_id,
        divisions(name, league_id, leagues(name)),
        home_team:teams!matches_home_team_id_fkey(id, name, division_id, divisions(name, leagues(name))),
        away_team:teams!matches_away_team_id_fkey(id, name, division_id, divisions(name, leagues(name)))
    ''').or_(f'home_team_id.eq.{nefc_id},away_team_id.eq.{nefc_id}').eq('season_id', 3).eq('age_group_id', 2).order('match_date').limit(20).execute()
    
    print(f"\n{'Date':<12} {'Match Div':<25} {'Home Team':<30} {'Home Div':<25} {'Away Team':<30} {'Away Div':<25}")
    print("=" * 170)
    
    for m in matches.data:
        match_div = m.get('divisions', {})
        match_div_name = f"{match_div.get('name', 'N/A')} ({match_div.get('leagues', {}).get('name', 'N/A')})"
        
        home = m['home_team']
        home_div = home.get('divisions', {})
        home_div_name = f"{home_div.get('name', 'N/A')} ({home_div.get('leagues', {}).get('name', 'N/A')})"
        
        away = m['away_team']
        away_div = away.get('divisions', {})
        away_div_name = f"{away_div.get('name', 'N/A')} ({away_div.get('leagues', {}).get('name', 'N/A')})"
        
        # Mark cross-league matches
        home_league = home_div.get('leagues', {}).get('name', 'N/A') if home_div else 'N/A'
        away_league = away_div.get('leagues', {}).get('name', 'N/A') if away_div else 'N/A'
        cross_league = "⚠️ CROSS-LEAGUE" if home_league != away_league else ""
        
        print(f"{m['match_date']:<12} {match_div_name:<25} {home['name']:<30} {home_div_name:<25} {away['name']:<30} {away_div_name:<25} {cross_league}")

