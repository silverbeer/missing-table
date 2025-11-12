#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

print("Testing division_id=7 (Academy - New England):\n")
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=7, match_type="League")
print(f"Teams in table: {len(table)}")
if len(table) > 0:
    print("\nFirst 10 teams:")
    for team in table[:10]:
        print(f"  {team['team']}: {team['played']} GP, {team['points']} Pts")
else:
    print("  (empty - no matches found with division_id=7)")
