#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Checking New England Surf SC matches:\n")

# Get the team
teams = db_conn.client.table('teams').select('id, name').ilike('name', '%Surf%').execute()
print("Teams matching 'Surf':")
for t in teams.data:
    print(f"  ID {t['id']}: {t['name']}")

if teams.data:
    team_id = teams.data[0]['id']
    print(f"\nMatches for team ID {team_id}:")
    
    # Get matches where this team is home or away
    matches = db_conn.client.table('matches').select('''
        id,
        match_date,
        division_id,
        home_score,
        away_score,
        divisions(id, name, league_id, leagues(name)),
        home_team:teams!matches_home_team_id_fkey(id, name),
        away_team:teams!matches_away_team_id_fkey(id, name)
    ''').or_(f'home_team_id.eq.{team_id},away_team_id.eq.{team_id}').eq('season_id', 3).eq('age_group_id', 2).order('match_date', desc=True).execute()
    
    print(f"\n{'Date':<12} {'Div':<4} {'Division':<25} {'League':<15} {'Score':<8} {'Home':<30} {'Away':<30}")
    print("=" * 140)
    
    for m in matches.data:
        div = m.get('divisions', {})
        league = div.get('leagues', {}) if div else {}
        score = f"{m.get('home_score', '-')}-{m.get('away_score', '-')}"
        print(f"{m['match_date']:<12} {m['division_id']:<4} {div.get('name', 'N/A'):<25} {league.get('name', 'N/A'):<15} {score:<8} {m['home_team']['name']:<30} {m['away_team']['name']:<30}")
    
    print(f"\nTotal matches: {len(matches.data)}")
    
    # Group by division
    by_div = {}
    for m in matches.data:
        div = m.get('divisions', {})
        div_name = f"{div.get('name', 'N/A')} (ID {m['division_id']})"
        by_div[div_name] = by_div.get(div_name, 0) + 1
    
    print("\nMatches by Division:")
    for div, count in sorted(by_div.items()):
        print(f"  {div}: {count} matches")
