#!/usr/bin/env python3
"""Test the table API with different divisions."""
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

print("Testing get_league_table with different divisions:\n")

# Test Homegrown (division_id=1)
print("=== Homegrown (division_id=1) ===")
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=1, match_type="League")
print(f"Teams in table: {len(table)}")
for team in table[:5]:
    print(f"  {team['team']}: {team['played']} GP, {team['points']} Pts")

print("\n=== Academy (division_id=2) ===")
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=2, match_type="League")
print(f"Teams in table: {len(table)}")
for team in table[:5]:
    print(f"  {team['team']}: {team['played']} GP, {team['points']} Pts")
