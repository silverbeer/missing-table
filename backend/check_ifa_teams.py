#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking IFA team records:\n")

# Get all teams with IFA in the name
ifa_teams = db_conn.client.table('teams').select('''
    id, name, league_id, division_id, club_id,
    leagues(name), divisions(name, leagues(name))
''').ilike('name', '%IFA%').execute()

print("Teams with 'IFA' in name:")
print(f"\n{'ID':<6} {'Name':<30} {'League':<15} {'Division':<25} {'Club ID':<10}")
print("=" * 100)
for team in ifa_teams.data:
    league = team.get('leagues', {})
    division = team.get('divisions', {})
    div_league = division.get('leagues', {}) if division else {}
    
    print(f"{team['id']:<6} {team['name']:<30} {league.get('name', 'NULL'):<15} {division.get('name', 'NULL'):<25} {team.get('club_id', 'NULL'):<10}")

# Check matches for each IFA team in U14 Homegrown
print("\n\nChecking U14 Homegrown (Division 1) matches for each IFA team:\n")

for team in ifa_teams.data:
    if team.get('division_id') == 1:  # Homegrown
        team_id = team['id']
        team_name = team['name']
        
        matches = db_conn.client.table('matches').select('id, match_date, home_score, away_score').or_(
            f'home_team_id.eq.{team_id},away_team_id.eq.{team_id}'
        ).eq('season_id', 3).eq('age_group_id', 2).eq('division_id', 1).execute()
        
        print(f"{team_name} (ID {team_id}):")
        print(f"  Total matches in U14 Homegrown: {len(matches.data)}")
        
        # Count completed matches
        completed = [m for m in matches.data if m.get('home_score') is not None and m.get('away_score') is not None]
        print(f"  Completed matches: {len(completed)}")

# Check if these are the same club
print("\n\nChecking club relationships:")
ifa_club = db_conn.client.table('clubs').select('*').ilike('name', '%IFA%').execute()
if ifa_club.data:
    print(f"\nIFA Clubs found:")
    for club in ifa_club.data:
        print(f"  ID {club['id']}: {club['name']} ({club.get('city', 'N/A')})")
        
        # Get teams for this club
        teams = db_conn.client.table('teams').select('id, name, division_id, divisions(name)').eq('club_id', club['id']).execute()
        print(f"    Teams in this club:")
        for t in teams.data:
            div = t.get('divisions', {})
            print(f"      - {t['name']} (ID {t['id']}, Division: {div.get('name', 'N/A')})")
else:
    print("  No IFA clubs found")
