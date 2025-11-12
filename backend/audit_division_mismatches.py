#!/usr/bin/env python3
"""
Audit and fix division_id mismatches in matches table.

This script finds matches where the division_id doesn't match the team's
assigned division for that age group, and generates SQL to fix them.
"""
import os
from collections import defaultdict
from dotenv import load_dotenv

# Load environment
load_dotenv()
env = os.getenv('APP_ENV', 'local')
load_dotenv(f'.env.{env}', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print(f"=== Division Mismatch Audit (Environment: {env}) ===\n")

# Step 1: Get all teams with their correct division assignments per age group
print("Step 1: Loading team division assignments...\n")

team_divisions = {}  # {team_id: {age_group_id: division_id}}

mappings = db_conn.client.table('team_mappings').select('''
    team_id,
    age_group_id,
    division_id,
    teams(id, name),
    age_groups(id, name),
    divisions(id, name, league_id, leagues(name))
''').execute()

for mapping in mappings.data:
    team_id = mapping['team_id']
    age_group_id = mapping['age_group_id']
    division_id = mapping['division_id']

    if team_id not in team_divisions:
        team_divisions[team_id] = {}

    team_divisions[team_id][age_group_id] = {
        'division_id': division_id,
        'team_name': mapping['teams']['name'],
        'age_group_name': mapping['age_groups']['name'],
        'division_name': mapping['divisions']['name'],
        'league_name': mapping['divisions']['leagues']['name'],
    }

print(f"Loaded {len(team_divisions)} teams with division assignments\n")

# Step 2: Check all matches for mismatches
print("Step 2: Auditing matches for division_id mismatches...\n")

mismatches = []
match_count = 0
seasons_to_check = [3]  # 2025-2026 season

for season_id in seasons_to_check:
    matches = db_conn.client.table('matches').select('''
        id,
        home_team_id,
        away_team_id,
        division_id,
        season_id,
        age_group_id,
        match_date,
        home_team:teams!matches_home_team_id_fkey(name),
        away_team:teams!matches_away_team_id_fkey(name),
        divisions(name, leagues(name))
    ''').eq('season_id', season_id).execute()

    match_count += len(matches.data)

    for match in matches.data:
        match_id = match['id']
        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']
        current_division_id = match['division_id']
        age_group_id = match['age_group_id']

        # Get correct division for home team
        home_correct = None
        if home_team_id in team_divisions and age_group_id in team_divisions[home_team_id]:
            home_correct = team_divisions[home_team_id][age_group_id]['division_id']

        # Get correct division for away team
        away_correct = None
        if away_team_id in team_divisions and age_group_id in team_divisions[away_team_id]:
            away_correct = team_divisions[away_team_id][age_group_id]['division_id']

        # Both teams should have the same correct division
        correct_division_id = home_correct if home_correct else away_correct

        # Check for mismatch
        if correct_division_id and current_division_id != correct_division_id:
            current_div_info = match.get('divisions') or {}
            current_div_name = current_div_info.get('name', 'Unknown') if current_div_info else 'Unknown'
            current_league_info = current_div_info.get('leagues') if current_div_info else None
            current_league_name = current_league_info.get('name', 'Unknown') if current_league_info else 'Unknown'

            # Get correct division name
            correct_div_info = None
            if home_team_id in team_divisions and age_group_id in team_divisions[home_team_id]:
                correct_div_info = team_divisions[home_team_id][age_group_id]
            elif away_team_id in team_divisions and age_group_id in team_divisions[away_team_id]:
                correct_div_info = team_divisions[away_team_id][age_group_id]

            mismatches.append({
                'match_id': match_id,
                'match_date': match['match_date'],
                'home_team': match['home_team']['name'],
                'away_team': match['away_team']['name'],
                'age_group_id': age_group_id,
                'current_division_id': current_division_id,
                'current_division_name': current_div_name,
                'current_league_name': current_league_name,
                'correct_division_id': correct_division_id,
                'correct_division_name': correct_div_info['division_name'] if correct_div_info else 'Unknown',
                'correct_league_name': correct_div_info['league_name'] if correct_div_info else 'Unknown',
            })

print(f"Audited {match_count} matches")
print(f"Found {len(mismatches)} matches with incorrect division_id\n")

# Step 3: Report findings
if mismatches:
    print("=" * 160)
    print(f"{'ID':<6} {'Date':<12} {'Home Team':<30} {'Away Team':<30} {'Current Division':<30} {'Correct Division':<30}")
    print("=" * 160)

    for m in mismatches[:20]:  # Show first 20
        current = f"{m['current_division_name']} ({m['current_league_name']})"
        correct = f"{m['correct_division_name']} ({m['correct_league_name']})"
        print(f"{m['match_id']:<6} {m['match_date']:<12} {m['home_team']:<30} {m['away_team']:<30} {current:<30} {correct:<30}")

    if len(mismatches) > 20:
        print(f"\n... and {len(mismatches) - 20} more mismatches")

    # Group by correction needed
    print("\n\nMismatches by correction needed:")
    by_correction = defaultdict(list)
    for m in mismatches:
        key = f"{m['current_division_name']} ({m['current_division_id']}) → {m['correct_division_name']} ({m['correct_division_id']})"
        by_correction[key].append(m['match_id'])

    for correction, match_ids in sorted(by_correction.items()):
        print(f"  {correction}: {len(match_ids)} matches")

    # Step 4: Generate SQL fix
    print("\n\n=== SQL Fix Statements ===\n")
    print("-- Backup matches table first!")
    print("-- CREATE TABLE matches_backup AS SELECT * FROM matches;\n")

    for correction, match_ids in sorted(by_correction.items()):
        parts = correction.split(' → ')
        from_div = parts[0].split('(')[1].split(')')[0]
        to_div = parts[1].split('(')[1].split(')')[0]

        print(f"-- {correction}")
        print(f"UPDATE matches")
        print(f"SET division_id = {to_div}")
        print(f"WHERE id IN ({', '.join(map(str, match_ids))});")
        print()

    print(f"\n-- Total matches to update: {len(mismatches)}")

    # Save SQL to file
    sql_file = f'fix_division_mismatches_{env}.sql'
    with open(sql_file, 'w') as f:
        f.write("-- Division Mismatch Fix SQL\n")
        f.write(f"-- Generated for environment: {env}\n")
        f.write(f"-- Total mismatches: {len(mismatches)}\n\n")
        f.write("-- IMPORTANT: Backup first!\n")
        f.write("-- CREATE TABLE matches_backup AS SELECT * FROM matches;\n\n")

        for correction, match_ids in sorted(by_correction.items()):
            parts = correction.split(' → ')
            to_div = parts[1].split('(')[1].split(')')[0]

            f.write(f"-- {correction}\n")
            f.write(f"UPDATE matches\n")
            f.write(f"SET division_id = {to_div}\n")
            f.write(f"WHERE id IN ({', '.join(map(str, match_ids))});\n\n")

        f.write(f"\n-- Total matches updated: {len(mismatches)}\n")

    print(f"\n✅ SQL saved to: {sql_file}")
    print(f"\nTo apply fixes:")
    print(f"1. Review the SQL file: cat {sql_file}")
    print(f"2. Run in Supabase SQL Editor or via CLI")

else:
    print("✅ No division_id mismatches found! Data is clean.")
