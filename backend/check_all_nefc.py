#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

# Get all NEFC teams
nefc_teams = db_conn.client.table('teams').select('''
    id, name, league_id, division_id,
    leagues(name), divisions(name, leagues(name))
''').ilike('name', '%NEFC%').execute()

print("All NEFC teams:\n")
for team in nefc_teams.data:
    league = team.get('leagues', {})
    division = team.get('divisions', {})
    div_league = division.get('leagues', {}) if division else {}
    print(f"ID {team['id']}: {team['name']}")
    print(f"  League: {league.get('name', 'N/A')}, Division: {division.get('name', 'N/A')}\n")

# Check team ID 22 (NEFC Homegrown)
nefc_homegrown_id = 22
print(f"\n{'='*150}")
print(f"Checking NEFC (ID {nefc_homegrown_id}) - Homegrown team - U14 matches:")
print(f"{'='*150}\n")

matches = db_conn.client.table('matches').select('''
    id, match_date, division_id,
    divisions(name, league_id, leagues(name)),
    home_team:teams!matches_home_team_id_fkey(id, name, league_id, division_id, divisions(name, leagues(name))),
    away_team:teams!matches_away_team_id_fkey(id, name, league_id, division_id, divisions(name, leagues(name)))
''').or_(f'home_team_id.eq.{nefc_homegrown_id},away_team_id.eq.{nefc_homegrown_id}').eq('season_id', 3).eq('age_group_id', 2).order('match_date').execute()

print(f"{'ID':<6} {'Date':<12} {'MDiv':<4} {'Match Division':<25} {'Home Team':<30} {'HDiv':<4} {'Away Team':<30} {'ADiv':<4} {'Issue':<20}")
print("=" * 170)

cross_league_count = 0
for m in matches.data:
    match_div = m.get('divisions', {})
    match_div_id = m['division_id']
    match_div_name = match_div.get('name', 'N/A') if match_div else 'N/A'
    match_league_name = match_div.get('leagues', {}).get('name', 'N/A') if match_div else 'N/A'
    
    home = m['home_team']
    home_div_id = home.get('division_id', 'NULL')
    home_league_name = home.get('divisions', {}).get('leagues', {}).get('name', 'N/A') if home.get('divisions') else 'N/A'
    
    away = m['away_team']
    away_div_id = away.get('division_id', 'NULL')
    away_league_name = away.get('divisions', {}).get('leagues', {}).get('name', 'N/A') if away.get('divisions') else 'N/A'
    
    # Determine issue
    issue = ""
    if home_league_name != away_league_name:
        issue = "⚠️ CROSS-LEAGUE"
        cross_league_count += 1
    
    print(f"{m['id']:<6} {m['match_date']:<12} {match_div_id:<4} {f'{match_div_name} ({match_league_name})':<25} {home['name']:<30} {home_div_id:<4} {away['name']:<30} {away_div_id:<4} {issue:<20}")

print(f"\nTotal matches: {len(matches.data)}")
print(f"Cross-league matches: {cross_league_count}")
