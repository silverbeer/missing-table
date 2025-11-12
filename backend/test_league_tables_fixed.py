#!/usr/bin/env python3
"""Test league tables after excluding cross-division matches."""
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

print("Testing league tables with cross-division matches excluded:\n")

# Test Homegrown (division_id=1)
print("="*80)
print("HOMEGROWN League (Division 1) - U14, 2025-2026")
print("="*80)
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=1, match_type="League")
print(f"\nTotal teams: {len(table)}")
print(f"\n{'Pos':<5} {'Team':<35} {'GP':<5} {'W':<5} {'D':<5} {'L':<5} {'Pts':<5}")
print("-" * 80)
for i, team in enumerate(table[:10], 1):
    print(f"{i:<5} {team['team']:<35} {team['played']:<5} {team['wins']:<5} {team['draws']:<5} {team['losses']:<5} {team['points']:<5}")

# Check for specific teams that shouldn't be there
academy_teams = ['Rhode Island Surf SC', 'Ginga FC', 'New England Surf SC', 'Connecticut Rush', 'IFA West']
found_academy = [t for t in table if t['team'] in academy_teams]
if found_academy:
    print(f"\n⚠️  WARNING: Found Academy teams in Homegrown table:")
    for t in found_academy:
        print(f"  - {t['team']} ({t['played']} GP)")
else:
    print(f"\n✅ No Academy teams in Homegrown table (correct!)")

# Test Academy (division_id=7)
print("\n" + "="*80)
print("ACADEMY League (Division 7) - U14, 2025-2026")
print("="*80)
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=7, match_type="League")
print(f"\nTotal teams: {len(table)}")
print(f"\n{'Pos':<5} {'Team':<35} {'GP':<5} {'W':<5} {'D':<5} {'L':<5} {'Pts':<5}")
print("-" * 80)
for i, team in enumerate(table[:10], 1):
    print(f"{i:<5} {team['team']:<35} {team['played']:<5} {team['wins']:<5} {team['draws']:<5} {team['losses']:<5} {team['points']:<5}")

# Check for specific teams that shouldn't be there
homegrown_teams = ['NEFC', 'FC Greater Boston Bolts', 'Oakwood Soccer Club', 'Bayside FC']
found_homegrown = [t for t in table if t['team'] in homegrown_teams]
if found_homegrown:
    print(f"\n⚠️  WARNING: Found Homegrown teams in Academy table:")
    for t in found_homegrown:
        print(f"  - {t['team']} ({t['played']} GP)")
else:
    print(f"\n✅ No Homegrown teams in Academy table (correct!)")
