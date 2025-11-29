# Unused Files Analysis - Backend Directory

## Summary
This document identifies files in the backend directory that appear to be unused, one-off scripts, or debugging artifacts that can likely be safely deleted.

## Categories

### 🔴 **SAFE TO DELETE** - One-off Fix Scripts (13 files)
These are scripts that were created to fix specific issues and are no longer needed:

1. `fix_division.py` - One-time fix for division issues
2. `fix_tom_profile.py` - One-time user profile fix
3. `fix_all_u13_divisions.py` - One-time U13 division fix
4. `fix_tsf_matches.py` - One-time TSF match fix
5. `fix_game_status.py` - One-time game status fix
6. `fix_missing_division_games.py` - One-time division game fix
7. `fix_sequence_robust.py` - One-time sequence fix (robust version)
8. `fix_sequence.py` - One-time sequence fix (original)
9. `fix_missing_division_id.py` - One-time division ID fix
10. `fix_duplicate_ifa_teams.py` - One-time duplicate team fix
11. `apply_rls_fix.py` - One-time RLS (Row Level Security) fix
12. `apply_club_id_migration.py` - One-time migration (already applied)
13. `apply_clubs_migration.py` - One-time migration (already applied)

**Recommendation**: ✅ **DELETE** - These are one-time fixes that have already been applied.

---

### 🔴 **SAFE TO DELETE** - Migration Scripts (Already Applied) (4 files)
These migrations have already been run and are no longer needed:

1. `apply_021_migration.py` - Migration 021 (already applied)
2. `apply_rls_migration.py` - RLS migration (already applied)
3. `migrate_mlsnext_data.py` - MLS Next data migration (one-time)
4. `import_u13_games_update.py` - U13 games import (one-time)

**Recommendation**: ✅ **DELETE** - Migrations are already applied. Keep migration history in git if needed.

---

### 🔴 **SAFE TO DELETE** - Backup/Restore Scripts (6 files)
One-time backup/restore operations:

1. `backup_dev_db.py` - One-time backup script
2. `restore_dev_backup.py` - One-time restore script
3. `restore_games.py` - One-time games restore
4. `restore_team_mappings.py` - One-time team mapping restore
5. `restore_teams_from_backup.py` - One-time teams restore
6. `backup_before_cleanup_20250930_085850.json` - Old backup file

**Recommendation**: ✅ **DELETE** - Backups should be in version control or external storage, not in codebase.

---

### 🔴 **SAFE TO DELETE** - Debugging/Inspection Scripts (8 files)
Temporary debugging and inspection scripts:

1. `inspect_db.py` - Database inspection script
2. `inspect_cloud_db.py` - Cloud database inspection
3. `check_match_status.py` - Match status checker
4. `check_schema_consistency.py` - Schema consistency checker
5. `check_teams_constraints.py` - Teams constraint checker
6. `check_teams_schema.py` - Teams schema checker
7. `simple_check.py` - Simple check script
8. `find_max_id.py` - Find max ID utility

**Recommendation**: ✅ **DELETE** - These were for troubleshooting specific issues. If needed again, can recreate.

---

### 🔴 **SAFE TO DELETE** - Old/Alternative App Files (1 file)
1. `app_sqlite.py` - Old SQLite-based app (replaced by app.py with Supabase)

**Recommendation**: ✅ **DELETE** - Superseded by current app.py. History preserved in git.

---

### 🟡 **REVIEW BEFORE DELETING** - Old DAO Files (3 files)
These might be referenced somewhere, but we now use `match_dao.py`:

1. `dao/enhanced_data_access.py` - Old DAO implementation
2. `dao/data_access.py` - Old SQLite DAO
3. `dao/local_data_access.py` - Old local DAO
4. `dao/supabase_data_access.py` - Old Supabase DAO

**Recommendation**: 🟡 **REVIEW** - Check if any tests or scripts still import these. If not, delete.

---

### 🟡 **REVIEW BEFORE DELETING** - Test/Debug Files (2 files)
1. `cli_test.py` - CLI testing script (might be useful for manual testing)
2. `test_async_match_submission.py` - Async match submission test

**Recommendation**: 🟡 **REVIEW** - These might be useful for manual testing. Check if they're documented or used.

---

### 🟡 **REVIEW BEFORE DELETING** - Utility Scripts (8 files)
These might be useful utilities:

1. `create_test_user.py` - Create test user utility
2. `create_admin_invite.py` - Create admin invite utility
3. `create_scraper_user.py` - Create scraper user utility
4. ✅ `create_service_account_token.py` - **MOVED** to `scripts/utilities/`
5. `validate_clubs.py` - Validate clubs utility
6. `validate_match_leagues.py` - Validate match leagues utility
7. `verify_match_id.py` - Verify match ID utility
8. `search_matches.py` - Match search utility (might be useful CLI tool)

**Recommendation**: 🟡 **REVIEW** - These might be useful utilities. Consider moving to `scripts/` directory if keeping.

---

### 🟡 **REVIEW BEFORE DELETING** - Setup/Population Scripts (7 files)
These might be needed for setup:

1. `setup_leagues_divisions.py` - Setup leagues/divisions
2. `setup_audit_trail.py` - Setup audit trail
3. `populate_teams.py` - Populate teams
4. `populate_teams_dev.py` - Populate teams (dev)
5. `populate_teams_simple.py` - Populate teams (simple)
6. `populate_teams_supabase.py` - Populate teams (Supabase)
7. `populate_team_match_types.py` - Populate team match types
8. `add_guest_teams.py` - Add guest teams
9. `create_clubs_table.py` - Create clubs table
10. `create_sample_matches.py` - Create sample matches

**Recommendation**: 🟡 **REVIEW** - These might be needed for initial setup or testing. Consider consolidating or moving to `scripts/setup/`.

---

### 🟡 **REVIEW BEFORE DELETING** - Sync/Migration Utilities (4 files)
1. `sync_local_to_dev.py` - Sync local to dev
2. `sync_local_from_dev_simple.py` - Sync local from dev
3. `sync_dev_schema.py` - Sync dev schema
4. `migration_status.py` - Migration status checker

**Recommendation**: 🟡 **REVIEW** - These might be useful for development workflow. Check if they're documented.

---

### 🔴 **SAFE TO DELETE** - Screenshot/Image Files (7 files)
Debugging screenshots:

1. `after_cookie_accept.png`
2. `after_filter_click.png`
3. `after_filter_set.png`
4. `calendar_step1_opened.png`
5. `calendar_step2_september.png`
6. `calendar_step4_range_selected.png`
7. `calendar_step5_applied.png`
8. `mlsnext_initial.png`
9. `mlsnext_page.png`
10. `mlsnext_results.png`

**Recommendation**: ✅ **DELETE** - These are debugging screenshots, not needed in codebase.

---

### 🔴 **SAFE TO DELETE** - Old Data Files (6 files)
Old CSV, DB, and JSON data files:

1. `mlsnext_u13_all_games_with_ids.csv` - Old CSV data
2. `mlsnext_u13_all_games.csv` - Old CSV data
3. `mlsnext_u13_teams.csv` - Old CSV data
4. `mlsnext_u13_fall.db` - Old SQLite database
5. `league.db` - Old SQLite database
6. `league_mismatches.json` - Old JSON data
7. `team_name_mappings.json` - Old mapping file
8. `team_name_to_id_mapping.json` - Old mapping file

**Recommendation**: ✅ **DELETE** - Old data files shouldn't be in codebase. Keep in external storage if needed.

---

### 🟡 **REVIEW BEFORE DELETING** - Documentation Files (1 file)
1. `DATA_FIXES_2024-11-12.md` - Documentation of data fixes

**Recommendation**: 🟡 **REVIEW** - Might be useful historical documentation. Consider moving to `docs/` if keeping.

---

### 🟡 **REVIEW BEFORE DELETING** - Special Files (2 files)
1. `minimal_app.py` - Minimal test app (documented in README_APPS.md as test-only)
2. `pyramid_visualizer.py` - Pyramid visualizer utility

**Recommendation**: 🟡 **REVIEW** - `minimal_app.py` is documented as test-only, might be useful. `pyramid_visualizer.py` - check if it's used.

---

### 🟡 **REVIEW BEFORE DELETING** - Backup Shell Scripts (2 files)
1. `scripts/start/start_supabase_cli.sh.bak` - Backup shell script
2. `scripts/start/start_local.sh.bak` - Backup shell script

**Recommendation**: ✅ **DELETE** - Backup files shouldn't be in repo.

---

## Summary Statistics

| Category | Count | Action |
|----------|-------|--------|
| **Safe to Delete** | **47 files** | ✅ DELETE |
| **Review Before Deleting** | **35 files** | 🟡 REVIEW |
| **Total** | **82 files** | |

## Recommended Action Plan

### Phase 1: Safe Deletions (47 files)
Delete all files marked as "Safe to Delete" - these are clearly one-off scripts, old data, or debugging artifacts.

### Phase 2: Review & Consolidate (35 files)
1. Check if any of the "Review" files are imported or referenced
2. Move useful utilities to `scripts/` directory
3. Consolidate similar scripts
4. Document any scripts that are kept

### Phase 3: Cleanup
1. Remove old backup files (`.bak`)
2. Remove screenshot files
3. Remove old data files (CSV, DB, JSON backups)

## Commands to Check Before Deleting

```bash
# Check if any files import the old DAO files
grep -r "from dao\.enhanced_data_access\|from dao\.data_access\|from dao\.local_data_access\|from dao\.supabase_data_access" backend/

# Check if app_sqlite is referenced
grep -r "app_sqlite" backend/

# Check if any test files import the review files
grep -r "import.*cli_test\|import.*test_async" backend/tests/
```

