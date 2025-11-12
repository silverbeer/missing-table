#!/usr/bin/env python3
import os
from dotenv import load_dotenv
load_dotenv()
load_dotenv('.env.dev', override=True)

from dao.enhanced_data_access_fixed import SupabaseConnection

db_conn = SupabaseConnection()

print("Comparing matches for IFA (123) vs IFA HG (19):\n")

# Get IFA matches
ifa_matches = db_conn.client.table('matches').select('''
    id, match_date, home_score, away_score,
    home_team:teams!matches_home_team_id_fkey(id, name),
    away_team:teams!matches_away_team_id_fkey(id, name)
''').or_('home_team_id.eq.123,away_team_id.eq.123').eq('season_id', 3).eq('age_group_id', 2).order('match_date').execute()

print(f"IFA (ID 123) - {len(ifa_matches.data)} matches:")
print(f"{'Date':<12} {'Home':<30} {'Score':<8} {'Away':<30}")
print("=" * 85)
for m in ifa_matches.data:
    score = f"{m.get('home_score', '-')}-{m.get('away_score', '-')}"
    print(f"{m['match_date']:<12} {m['home_team']['name']:<30} {score:<8} {m['away_team']['name']:<30}")

# Get IFA HG matches
ifa_hg_matches = db_conn.client.table('matches').select('''
    id, match_date, home_score, away_score,
    home_team:teams!matches_home_team_id_fkey(id, name),
    away_team:teams!matches_away_team_id_fkey(id, name)
''').or_('home_team_id.eq.19,away_team_id.eq.19').eq('season_id', 3).eq('age_group_id', 2).order('match_date').execute()

print(f"\n\nIFA HG (ID 19) - {len(ifa_hg_matches.data)} matches:")
print(f"{'Date':<12} {'Home':<30} {'Score':<8} {'Away':<30}")
print("=" * 85)
for m in ifa_hg_matches.data:
    score = f"{m.get('home_score', '-')}-{m.get('away_score', '-')}"
    print(f"{m['match_date']:<12} {m['home_team']['name']:<30} {score:<8} {m['away_team']['name']:<30}")

# Check for duplicate opponents
print("\n\nAnalysis:")
print("=========")

# Get opponent names for IFA
ifa_opponents = set()
for m in ifa_matches.data:
    if m['home_team']['id'] == 123:
        ifa_opponents.add(m['away_team']['name'])
    else:
        ifa_opponents.add(m['home_team']['name'])

# Get opponent names for IFA HG
ifa_hg_opponents = set()
for m in ifa_hg_matches.data:
    if m['home_team']['id'] == 19:
        ifa_hg_opponents.add(m['away_team']['name'])
    else:
        ifa_hg_opponents.add(m['home_team']['name'])

print(f"IFA opponents: {sorted(ifa_opponents)}")
print(f"IFA HG opponents: {sorted(ifa_hg_opponents)}")

# Check for overlaps
overlap = ifa_opponents & ifa_hg_opponents
if overlap:
    print(f"\n⚠️  Common opponents (suggests duplicate teams): {sorted(overlap)}")
else:
    print(f"\n✅ No common opponents (they might be legitimately separate teams)")

# Recommendation
print("\n\nRecommendation:")
if len(ifa_matches.data) < len(ifa_hg_matches.data):
    print(f"  'IFA' (123) has only {len(ifa_matches.data)} matches vs 'IFA HG' (19) with {len(ifa_hg_matches.data)} matches")
    print(f"  This suggests 'IFA' might be a duplicate or test data that should be:")
    print(f"    1. Deleted (if it's duplicate data), OR")
    print(f"    2. Merged with IFA HG (if matches should belong to IFA HG)")
