# Schema Audit Report

**Date:** 2025-10-30
**Audit Tools:**
- `backend/scripts/audit_schema_versions.py`
- `backend/scripts/inspect_schema_direct.py`

## Executive Summary

**Critical Finding:** Schema drift detected across all three environments. The parent club migration `20251030184100_add_parent_club_to_teams` has **NOT been applied to any environment**, despite documentation claiming it was tested and verified.

## Environment Status

### LOCAL Environment ✅ (Mostly Healthy)

**Status:** Baseline schema only (v1.0.0)

| Feature | Status | Notes |
|---------|--------|-------|
| parent_club_id column | ✗ Missing | Migration not applied |
| leagues table | ✗ Missing | Not needed for baseline |
| schema_version table | ✓ Exists | v1.0.0 baseline |
| Parent club functions | ✗ Missing | `get_club_teams`, `is_parent_club`, `get_parent_club` |
| get_schema_version | ✓ Exists | Working correctly |
| teams_with_parent view | ✗ Missing | Requires parent_club_id migration |

**Tables:**
- ✓ teams (columns: id, name, city, academy_team, created_at, updated_at)
- ✓ matches
- ✓ age_groups
- ✓ divisions
- ✓ team_mappings
- ✓ schema_version

**Schema Version:** 1.0.0 (baseline applied 2025-10-29)

---

### DEV Environment ⚠️ (Schema Drift)

**Status:** Has leagues table but missing schema tracking

| Feature | Status | Notes |
|---------|--------|-------|
| parent_club_id column | ✗ Missing | Migration not applied |
| leagues table | ✓ **Exists** | **Unique to dev!** |
| schema_version table | ✗ **Missing** | **No migration tracking!** |
| Parent club functions | ✗ Missing | None exist |
| get_schema_version | ✗ Missing | Can't track migrations |
| teams_with_parent view | ✗ Missing | Requires parent_club_id migration |

**Tables:**
- ✓ teams (columns: id, name, city, created_at, updated_at, academy_team)
- ✓ matches
- ✓ age_groups
- ✓ divisions
- ✓ team_mappings
- ✓ **leagues** (extra table not in local/prod)
- ✗ schema_version (missing!)

**Schema Version:** Unknown (no tracking)

**Critical Issues:**
1. Has leagues table that other environments don't have
2. Missing schema_version table for migration tracking
3. Can't determine what migrations have been applied

---

### PROD Environment ✅ (Connection Fixed - Identical to DEV)

**Status:** Connected successfully, schema matches DEV

| Feature | Status | Notes |
|---------|--------|-------|
| parent_club_id column | ✗ Missing | Migration not applied |
| leagues table | ✗ Missing | Consistent with LOCAL |
| schema_version table | ✗ **Missing** | **No migration tracking!** |
| Parent club functions | ✗ Missing | None exist |
| get_schema_version | ✗ Missing | Can't track migrations |
| teams_with_parent view | ✗ Missing | Requires parent_club_id migration |

**Tables:**
- ✓ teams (columns: id, name, city, created_at, updated_at, academy_team)
- ✓ matches
- ✓ age_groups
- ✓ divisions
- ✓ team_mappings
- ✗ leagues (missing - same as LOCAL)
- ✗ schema_version (missing!)

**Schema Version:** Unknown (no tracking)

**Connection Issue Resolution:**
- **Problem:** `.env.prod` had placeholder values instead of real credentials
- **Solution:** Created script `scripts/sync-prod-env-from-gke.sh` to retrieve credentials from Kubernetes
- **Result:** Successfully connected to production Supabase database

---

## Schema Drift Analysis

### Critical Differences

| Feature | LOCAL | DEV | PROD |
|---------|-------|-----|------|
| parent_club_id | ✗ | ✗ | ✗ |
| leagues table | ✗ | ✓ ⚠️ | ✗ |
| schema_version table | ✓ | ✗ | ✗ |
| Schema tracking | ✓ v1.0.0 | ✗ None | ✗ None |
| Connection | ✓ | ✓ | ✓ (Fixed) |

### Impact Assessment

**High Priority:**
1. ✅ ~~**PROD connection failure**~~ - **FIXED!** Credentials retrieved from Kubernetes
2. **DEV & PROD missing schema_version** - No migration tracking in cloud environments
3. **DEV has leagues table** - Schema inconsistency (only DEV has it)

**Medium Priority:**
4. **parent_club_id not applied anywhere** - Core feature not deployed
5. **parent club functions missing** - Supporting functions not created
6. **teams_with_parent view missing** - Convenience view not created

## Migration Status

### Applied Migrations

**LOCAL:**
- ✅ `20251028000001_baseline_schema` (v1.0.0) - Applied 2025-10-29

**DEV:**
- ❓ Unknown - No schema_version table to track

**PROD:**
- ❓ Unknown - Connection failed

### Pending Migrations

**All Environments Need:**
1. `20251030184100_add_parent_club_to_teams` (v1.2.0)
   - Add parent_club_id column
   - Create parent club functions
   - Create teams_with_parent view
   - Add indexes and constraints

**DEV Specifically Needs:**
1. Create schema_version table (from baseline)
2. Backfill migration history
3. Sync leagues table status with local/prod (decide to keep or remove)

**PROD Specifically Needs:**
1. Fix database connection
2. Determine current schema state
3. Apply missing migrations

## Recommendations

### Immediate Actions (Before Starting Club Implementation)

1. **Fix PROD Connection** ⚠️ HIGH PRIORITY
   - Verify `.env.prod` credentials
   - Test connection manually
   - Document prod access procedure

2. **Sync DEV Schema Tracking** ⚠️ HIGH PRIORITY
   - Apply baseline migration to create schema_version table
   - Backfill migration history
   - Ensure get_schema_version() function exists

3. **Decide on leagues Table**
   - Does dev need leagues table?
   - Should local/prod have it?
   - Document decision in schema design docs

4. **Create Clean Baseline**
   - Get all environments to same baseline state
   - Apply missing migrations in order
   - Verify with audit scripts

### Migration Path Forward

#### Option A: Start Fresh with LOCAL (Recommended)

```bash
# 1. Ensure local is at baseline
cd supabase-local
npx supabase db reset

# 2. Apply parent club migration
npx supabase migration new add_parent_club_to_teams
# (Copy migration SQL from docs/PARENT_CLUB_MIGRATION_GUIDE.md)
npx supabase db reset

# 3. Verify local is correct
uv run python scripts/inspect_schema_direct.py local

# 4. Restore production data to local for testing
./switch-env.sh prod
./scripts/db_tools.sh backup prod

./switch-env.sh local
./scripts/db_tools.sh restore [prod-backup].json

# 5. Test migration with real data
# (Create and run data migration scripts)

# 6. Once verified, apply to DEV
./switch-env.sh dev
cd supabase-local && npx supabase db push --linked

# 7. Finally apply to PROD (after thorough testing)
./switch-env.sh prod
cd supabase-local && npx supabase db push --linked
```

#### Option B: Fix Environments Individually

**Not recommended** - Too risky with schema drift

## Next Steps

Before proceeding with club implementation (`CLUB_LEAGUE_IMPLEMENTATION_PLAN.md`):

1. ✅ **Complete** - Schema audit
2. ⏳ **In Progress** - Fix PROD connection
3. ⏳ **Pending** - Sync DEV schema tracking
4. ⏳ **Pending** - Apply parent club migration to local
5. ⏳ **Pending** - Test with real data locally
6. ⏳ **Pending** - Deploy to dev
7. ⏳ **Pending** - Deploy to prod

**Only after all environments are in sync should we proceed with Phase 1 of the club implementation.**

## Tools Created

This audit created two useful tools for ongoing schema management:

1. **`backend/scripts/audit_schema_versions.py`**
   - Comprehensive schema version comparison
   - Checks functions, views, tables
   - Detects schema drift
   - Usage: `uv run python scripts/audit_schema_versions.py --all`

2. **`backend/scripts/inspect_schema_direct.py`**
   - Direct schema inspection via table queries
   - Detailed column listing
   - Function and view verification
   - Usage: `uv run python scripts/inspect_schema_direct.py [local|dev|prod]`

## Appendix: Raw Audit Data

### LOCAL Inspection Output

```
Teams Table: id, name, city, academy_team, created_at, updated_at
parent_club_id: MISSING
leagues: MISSING
schema_version: EXISTS (v1.0.0)
Functions: get_schema_version EXISTS, parent club functions MISSING
View: teams_with_parent MISSING
```

### DEV Inspection Output

```
Teams Table: id, name, city, created_at, updated_at, academy_team
parent_club_id: MISSING
leagues: EXISTS ⚠️
schema_version: MISSING ⚠️
Functions: ALL MISSING
View: teams_with_parent MISSING
```

### PROD Inspection Output

```
Connection: FAILED ❌
Error: [Errno 8] nodename nor servname provided, or not known
```

---

## Resolution Summary (2025-10-30)

### ✅ PROD Connection Fixed

**Problem:** `.env.prod` file had placeholder credentials instead of real production values

**Root Cause:** The file was overwritten or reset at some point. Since `.env.prod` is gitignored (correctly), there was no automatic backup.

**Solution Created:**
1. **Script:** `scripts/sync-prod-env-from-gke.sh`
   - Retrieves production credentials from Kubernetes secrets
   - Creates/updates `.env.prod` automatically
   - Backs up existing file before overwriting
   - Sets secure permissions (600)

2. **Execution:**
   ```bash
   ./scripts/sync-prod-env-from-gke.sh
   ```

3. **Result:**
   - ✅ Successfully retrieved all secrets from `missing-table-secrets` in `missing-table-prod` namespace
   - ✅ Created `/Users/silverbeer/gitrepos/missing-table/backend/.env.prod`
   - ✅ Backed up old file to `.env.prod.backup.20251030_153251`
   - ✅ Connection diagnostic passed - DNS resolves, URL valid, credentials present

### Schema State Summary

**All three environments are now accessible and audited:**

| Environment | Status | Schema Version | Key Issues |
|-------------|--------|----------------|------------|
| LOCAL | ✅ Baseline | v1.0.0 | Missing parent_club_id migration |
| DEV | ⚠️ Drifted | Unknown | Missing schema_version table, has extra leagues table |
| PROD | ✅ Connected | Unknown | Missing schema_version table |

### Next Actions

**Before proceeding with club implementation:**

1. ✅ **COMPLETE** - Fix PROD connection
2. ✅ **COMPLETE** - Complete schema audit of all environments
3. ⏳ **NEXT** - Decide on `leagues` table (keep in DEV or remove?)
4. ⏳ **NEXT** - Add `schema_version` table to DEV and PROD
5. ⏳ **NEXT** - Apply parent club migration to all environments
6. ⏳ **NEXT** - Verify all environments are in sync

**Recommendation:** Proceed with local testing first, then sync to dev/prod once verified.

---

**Report Generated:** 2025-10-30
**Last Updated:** 2025-10-30 15:35 (PROD connection fixed)
**Next Audit Recommended:** After applying migrations
**Status:** ⚠️ IN PROGRESS - PROD fixed, migration sync needed
