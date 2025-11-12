#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import EnhancedSportsDAO, SupabaseConnection

db_conn = SupabaseConnection()
dao = EnhancedSportsDAO(db_conn)

print("Testing IFA fix - checking league tables:\n")

# Homegrown table
print("="*80)
print("HOMEGROWN (Division 1) - Checking for IFA teams")
print("="*80)
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=1, match_type="League")
ifa_teams = [t for t in table if 'IFA' in t['team']]
print(f"\nIFA teams in Homegrown table:")
if ifa_teams:
    for t in ifa_teams:
        print(f"  - {t['team']}: {t['played']} GP, {t['points']} Pts")
else:
    print("  (none - only non-IFA Homegrown teams)")

# Academy table
print("\n" + "="*80)
print("ACADEMY (Division 7) - Checking for IFA teams")
print("="*80)
table = dao.get_league_table(season_id=3, age_group_id=2, division_id=7, match_type="League")
ifa_teams = [t for t in table if 'IFA' in t['team']]
print(f"\nIFA teams in Academy table:")
if ifa_teams:
    for t in ifa_teams:
        print(f"  - {t['team']}: {t['played']} GP, {t['points']} Pts")
else:
    print("  (none)")

print("\n" + "="*80)
print("Expected result:")
print("  Homegrown: IFA HG only")
print("  Academy: IFA, IFA West, IFA Academy")
print("="*80)
