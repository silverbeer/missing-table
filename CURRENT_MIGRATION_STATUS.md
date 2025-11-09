# Current Migration Status - 2025-11-09

## What We've Accomplished

✅ **Created diagnostic tools:**
- `backend/check_schema_consistency.py` - Shows exact differences between environments
- `backend/apply_021_migration.py` - Helper to apply single migrations
- `backend/check_match_status.py` - Diagnostic for match_status column

✅ **Applied migrations successfully:**
- Local: **9 migrations** applied (latest: 1.3.1 - remove_team_aliases)
- Dev: **5 migrations** applied (latest: 1.3.1 - remove_team_aliases, just now)

✅ **Fixed critical issue:**
- Added `updated_at` trigger to both local and dev
- Migration 021 now works correctly with ENUM type

## Current State (As of Right Now)

### Migration Counts
- **Local**: 6 migrations tracked in schema_version
- **Dev**: 5 migrations tracked in schema_version

### Key Differences Remaining

1. **`team_aliases` table**
   - EXISTS in dev
   - MISSING in local
   - Reason: Local applied migration 20251101000001 which removes it
   - Impact: Low (being phased out)

2. **`matches` table column types**
   - `match_id`: local=VARCHAR, dev=TEXT
   - `match_status`: local=ENUM, dev=VARCHAR
   - `mls_match_id`: local=VARCHAR, dev=BIGINT
   - Impact: Medium (type mismatches could cause issues)

3. **`teams` table**
   - `division_id`: EXISTS in local, MISSING in dev
   - Impact: High (schema structure difference)

4. **Triggers**
   - `handle_updated_at`: EXISTS in dev (just added), MISSING in local
   - Other triggers: Different between environments
   - Impact: Medium (functional differences)

## The Core Problem

**Dev and local have diverged** due to:
1. Migrations applied in different orders
2. Some migrations only applied to one environment
3. Manual schema changes made directly in Supabase Dashboard
4. Migration 20251104185315 tries to add division_id to teams, but dev's teams table has no team_mappings to populate from

## Options Going Forward

### Option A: Make Dev the Source of Truth (Safest for Prod)
**Pros:**
- Dev is closest to production
- Less risk of data loss in prod
- Conservative approach

**Cons:**
- Local loses the newer migrations (division_id, etc.)
- Means rolling back some recent work

**Steps:**
1. Export dev schema completely
2. Drop and recreate local from dev schema
3. Going forward: local → dev → prod (always)

### Option B: Make Local the Source of Truth (Move Forward)
**Pros:**
- Local has newer, better schema (division_id)
- Represents the direction we want to go

**Cons:**
- Need to carefully migrate dev data
- Riskier if dev has important data
- Migration 20251104185315 needs data migration

**Steps:**
1. Manually fix dev to match local:
   - Add division_id column
   - Populate from team_mappings (or default)
   - Apply remaining migrations
2. Apply updated_at trigger to local
3. Verify both match

### Option C: Nuclear - Fresh Start Both (Clean Slate)
**Pros:**
- Guaranteed consistency
- Fresh baseline
- No legacy baggage

**Cons:**
- Lose all data in local and dev
- Most disruptive

**Steps:**
1. Create new baseline migration from desired schema
2. Drop and recreate both databases
3. Apply baseline
4. Start migration discipline from scratch

## Recommendation

**Option B - Make Local the Source of Truth**

Why:
1. Local has the newer, better schema with division_id
2. Dev likely doesn't have critical data (you can verify)
3. Moves us forward rather than backward
4. The division_id migration can be fixed with a default value

## Next Steps (If You Approve Option B)

1. **Fix division_id in dev** (5 minutes)
   ```sql
   -- Add column
   ALTER TABLE teams ADD COLUMN division_id INTEGER;

   -- Set to a default division
   UPDATE teams SET division_id = (SELECT id FROM divisions LIMIT 1);

   -- Make NOT NULL
   ALTER TABLE teams ALTER COLUMN division_id SET NOT NULL;

   -- Add foreign key
   ALTER TABLE teams ADD CONSTRAINT teams_division_id_fkey
   FOREIGN KEY (division_id) REFERENCES divisions(id);
   ```

2. **Apply remaining migrations to dev** (2 minutes)
   - 20251104185315_fix_teams_uniqueness_constraint.sql

3. **Apply updated_at trigger to local** (1 minute)
   - Already have the script: `apply_021_migration.py --env local`

4. **Verify sync** (1 minute)
   - Run: `check_schema_consistency.py`

5. **Document the process** (10 minutes)
   - Create MIGRATION_WORKFLOW.md
   - Add to team docs

## The Disciplined Process Going Forward

Once synced, here's the iron-clad process:

1. **Create migration file** in `supabase-local/migrations/`
   ```
   YYYYMMDDHHMMSS_description.sql
   ```

2. **Test locally first**
   ```bash
   uv run python scripts/apply_migrations_to_env.py --env local
   uv run python check_schema_consistency.py  # Should show local ahead
   ```

3. **Apply to dev**
   ```bash
   uv run python scripts/apply_migrations_to_env.py --env dev
   uv run python check_schema_consistency.py  # Should show IDENTICAL
   ```

4. **Apply to prod** (after testing dev 24-48 hours)
   ```bash
   uv run python scripts/apply_migrations_to_env.py --env prod
   # Or use Supabase Dashboard for safety
   ```

5. **Always verify**
   ```bash
   uv run python check_schema_consistency.py
   ```

## Files Created During This Session

1. `backend/check_schema_consistency.py` - Essential tool
2. `backend/apply_021_migration.py` - Migration helper
3. `backend/check_match_status.py` - Diagnostic tool
4. `backend/sql/021_add_updated_at_trigger.sql` - The migration
5. `backend/docs/021_APPLY_MIGRATION.md` - Documentation
6. `APPLY_UPDATED_AT_MIGRATION.md` - Quickstart guide
7. `DATABASE_MIGRATION_PROBLEM_AND_SOLUTION.md` - Analysis
8. This file - Current status

## Decision Time

**What do you want to do?**

A. Make dev the source of truth (roll back local)
B. Make local the source of truth (fix and upgrade dev) ← **RECOMMENDED**
C. Nuclear option (fresh start both)
D. Something else

Let me know and I'll execute immediately.
