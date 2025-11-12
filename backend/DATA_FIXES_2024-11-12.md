# Data Fixes Applied - 2024-11-12

## Summary
Applied team mapping corrections for 14 Academy league matches that were incorrectly assigned to Homegrown team versions.

## Issue
Three Academy teams (Valeo, FC Greater Boston Bolts, Rochester NY FC) had matches against Academy opponents that were incorrectly using their Homegrown team IDs instead of their Academy team IDs.

## Root Cause
The match-scraper matched team names without considering league context, resulting in:
- Homegrown versions being used for Academy league matches
- Incorrect division_id assignments
- Cross-division match filtering issues

## Fixes Applied

### Valeo Futbol Club (ID 27) → Valeo Futbol Club Academy (ID 179)
- Match 688: Valeo @ Seacoast United Mass
- Match 656: Valeo vs Syracuse Development Academy
- Match 719: Valeo vs Seacoast United Bedford
- Match 723: Valeo @ NEFC South

### FC Greater Boston Bolts (ID 17) → FC Greater Boston Bolts Academy (ID 178)
- Match 687: FC Greater Boston Bolts vs NEFC South
- Match 671: FC Greater Boston Bolts vs Seacoast United Bedford
- Match 695: FC Greater Boston Bolts @ New England Surf SC
- Match 714: FC Greater Boston Bolts @ Syracuse Development Academy
- Match 722: FC Greater Boston Bolts vs Seacoast United Mass

### Rochester NY FC (ID 25) → Rochester NY FC Academy (ID 180)
- Match 659: Rochester NY FC @ Seacoast United Bedford
- Match 667: Rochester NY FC vs New England Surf SC
- Match 692: Rochester NY FC vs New York Rush
- Match 705: Rochester NY FC @ Seacoast United Mass
- Match 704: Rochester NY FC @ NEFC South

## Result
- All 14 matches now correctly use Academy team IDs
- All matches have division_id=7 (Academy)
- No cross-division matches remain in Academy league
- League tables now correctly reflect same-division matches only

## Related Commits
- cedc618: Fix team mappings for matches 727 and 730
- 007da63: Correct division_id for IFA Academy home matches
- 017b575: Filter cross-division matches from league-grouped views

## Verification
Run the following diagnostic scripts to verify:
```bash
cd backend
APP_ENV=dev uv run python check_academy_team_matches.py
APP_ENV=dev uv run python check_homegrown_counterparts.py
```

## Future Prevention
Consider enhancing match-scraper with:
- League-aware team name matching
- DB-level validation for cross-division matches
- Automated checks for team/division consistency
