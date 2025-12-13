# Database Migration Workflow - THE IRON LAW

**Last Updated:** 2025-11-09
**Status:** ✅ Local and Dev are NOW IN SYNC

---

## 🔒 The Iron Law of Migrations

**ALWAYS: Local → Dev → Prod. NO EXCEPTIONS.**

Never apply migrations directly in Supabase Dashboard.
Never skip environments.
Never apply out of order.

---

## ✅ Current State (As of 2025-11-09)

### Databases Are In Sync
- ✅ **Local**: 8 migrations applied (latest: 1.5.0 - updated_at trigger)
- ✅ **Dev**: 8 migrations applied (latest: 1.5.0 - updated_at trigger)
- ✅ **Structural differences resolved**
- ✅ **Core tables (teams, clubs, leagues) identical**

### Known Acceptable Differences (Legacy)
These differences are from different baseline migrations and are functionally compatible:

**Column Types:**
- `matches.match_id`: local=VARCHAR, dev=TEXT (both work fine)
- `matches.match_status`: local=ENUM, dev=VARCHAR (both work fine)
- `matches.mls_match_id`: local=VARCHAR, dev=BIGINT (both work fine)

**Triggers:**
- `update_invitations_updated_at`: exists in dev only (not critical)
- `user_profiles_updated_at_trigger`: exists in dev only (not critical)

**Impact:** None. Going forward, all new migrations will be identical.

### Data Preserved
- ✅ **Dev data**: 28 teams, 401 matches - ALL PRESERVED
- ✅ **Local data**: Fresh baseline
- ✅ **division_id**: All teams have valid division_id

---

## 📋 Step-by-Step Migration Process

### 1. Create Migration File

```bash
cd /Users/silverbeer/gitrepos/missing-table

# Create migration with timestamp
DATE=$(date +%Y%m%d%H%M%S)
touch supabase-local/migrations/${DATE}_your_description.sql

# Edit the file
code supabase-local/migrations/${DATE}_your_description.sql
```

**Migration file template:**
```sql
-- Migration: [Brief description]
-- Date: YYYY-MM-DD
-- Version: X.Y.Z

-- Your SQL here
-- Always use IF EXISTS / IF NOT EXISTS for safety
-- Include comments explaining WHY

-- Example:
ALTER TABLE matches
ADD COLUMN IF NOT EXISTS new_field VARCHAR(100);

COMMENT ON COLUMN matches.new_field IS 'Purpose of this field';
```

---

### 2. Test on Local FIRST

```bash
cd backend

# Apply to local
uv run python scripts/apply_migrations_to_env.py --env local

# Verify it worked
uv run python check_schema_consistency.py
```

**Expected output:**
```
local:
  schema_version: X migrations
  Latest: (version, 'YYYYMMDDHHMMSS_your_description')

dev:
  schema_version: X-1 migrations  # One behind
```

**If it fails:**
- Fix the migration SQL
- Drop and recreate local database
- Try again

---

### 3. Apply to Dev

```bash
# Verify local is ahead
uv run python check_schema_consistency.py

# Apply to dev
uv run python scripts/apply_migrations_to_env.py --env dev

# Verify they match
uv run python check_schema_consistency.py
```

**Expected output:**
```
================================================================================
SUMMARY
================================================================================
✅ All environments appear to be in sync
```

**If they don't match:**
- STOP
- Review what's different
- Fix manually if needed
- Never proceed to prod until local == dev

---

### 4. Test in Dev (24-48 hours)

**Before applying to prod:**
- ✅ Test the feature that required the migration
- ✅ Check logs for errors
- ✅ Monitor for 24-48 hours
- ✅ Run check_schema_consistency.py again

---

### 5. Apply to Prod

```bash
cd backend

# DOUBLE CHECK you're ready
uv run python check_schema_consistency.py

# Apply to prod (safest: use Supabase Dashboard)
# Option A: Dashboard (RECOMMENDED)
cat supabase-local/migrations/YYYYMMDDHHMMSS_your_description.sql
# Copy/paste into Supabase Dashboard SQL Editor for prod project

# Option B: Script (if you have prod access)
uv run python apply_migrations_to_env.py --env prod
```

**After applying to prod:**
```bash
# Verify (when you add prod to check_schema_consistency.py)
uv run python check_schema_consistency.py
```

---

## 🚫 What NOT To Do

### ❌ NEVER Do These Things

1. **Never apply migrations via Supabase Dashboard directly**
   - Always use the script or SQL files tracked in git

2. **Never skip local testing**
   - Always test on local first

3. **Never skip dev**
   - Never go Local → Prod
   - Always go Local → Dev → Prod

4. **Never apply migrations out of order**
   - Migrations must be applied in timestamp order

5. **Never modify applied migrations**
   - Once applied, create a new migration to fix
   - Never edit and re-apply

6. **Never commit without testing**
   - Test locally before committing migration file

7. **Never apply to prod without dev soak time**
   - Wait 24-48 hours after dev deployment

---

## 🛠️ Tools You Have

### check_schema_consistency.py
**Purpose:** Verify all environments match

```bash
cd backend
uv run python check_schema_consistency.py
```

Shows:
- Migration counts
- Table differences
- Column type mismatches
- Trigger differences
- ENUM value differences

**Use it:**
- Before applying to next environment
- After applying migrations
- When debugging schema issues
- Weekly as a health check

### apply_migrations_to_env.py
**Purpose:** Apply all pending migrations to an environment

```bash
cd backend
uv run python scripts/apply_migrations_to_env.py --env local
uv run python scripts/apply_migrations_to_env.py --env dev
uv run python scripts/apply_migrations_to_env.py --env prod
```

**⚠️ IMPORTANT:** This script tries to apply ALL migrations, even already-applied ones.
It relies on "already exists" errors to skip them. This causes error messages like:

```
✗ Error: cannot change return type of existing function
```

**This is NORMAL and EXPECTED** if your databases are already in sync!

**When to use it:**
- ONLY when you create a NEW migration file
- NOT for checking status (use check_schema_consistency.py instead)

**Why it errors:**
- The script doesn't check schema_version before applying
- It tries to reapply everything
- Some migrations can't be reapplied (like function changes)
- If all your migrations are already applied, it will error - this is fine!

### apply_021_migration.py (Template)
**Purpose:** Example of applying a single migration

```bash
cd backend
uv run python apply_021_migration.py --env local
```

**Use this as a template** for one-off migration scripts when needed.

---

## 📁 Migration File Organization

### Single Source of Truth
```
supabase-local/migrations/
├── 20251028000001_baseline_schema.sql
├── 20251029163754_add_league_layer.sql
├── 20251030184100_add_parent_club_to_teams.sql
├── 20251101000000_add_clubs_table.sql
├── 20251101000001_remove_team_aliases.sql
├── 20251104185315_fix_teams_uniqueness_constraint.sql
└── YYYYMMDDHHMMSS_your_new_migration.sql
```

### Migration Naming Convention
```
YYYYMMDDHHMMSS_brief_description.sql

Examples:
20251109143000_add_player_stats.sql
20251109150000_fix_match_scores_type.sql
20251110120000_add_team_logo_url.sql
```

---

## 🔍 Verification Checklist

Before considering a migration "done":

- [ ] Migration file created in `supabase-local/migrations/`
- [ ] Tested on local successfully
- [ ] check_schema_consistency.py shows local ahead
- [ ] Applied to dev successfully
- [ ] check_schema_consistency.py shows local == dev
- [ ] Tested feature in dev
- [ ] Waited 24-48 hours
- [ ] No errors in dev logs
- [ ] Applied to prod
- [ ] Verified prod working
- [ ] Migration file committed to git
- [ ] Updated MIGRATION_WORKFLOW.md if process changed

---

## 🆘 Emergency Procedures

### If Migration Fails on Dev

1. **Don't panic**
2. Check the error message
3. Fix the SQL
4. If needed: manually rollback dev
5. Re-apply corrected migration
6. Never proceed to prod with a failed dev migration

### If Migration Fails on Prod

1. **Immediate rollback**
   ```sql
   -- Document what you're rolling back
   -- Execute rollback SQL
   ```

2. **Notify team**
3. **Investigate in dev**
4. **Create fix migration**
5. **Test fix: Local → Dev → (wait) → Prod**

### If Databases Drift

1. **Run check_schema_consistency.py**
2. **Document differences**
3. **Create migration to fix drift**
4. **Apply using normal process**
5. **Verify sync restored**

---

## 📊 Health Checks

### Weekly
```bash
cd backend
uv run python check_schema_consistency.py > schema_health_$(date +%Y%m%d).txt
```

Review output. Should show: "✅ All environments appear to be in sync"

### Before Major Releases
```bash
# Verify all environments match
uv run python check_schema_consistency.py

# Check migration history
psql $DATABASE_URL -c "SELECT * FROM schema_version ORDER BY id"
```

---

## 🎯 Success Criteria

You're doing it right if:
- ✅ check_schema_consistency.py always shows sync
- ✅ All migrations tracked in git
- ✅ All migrations in `schema_version` table
- ✅ No manual schema changes in Supabase Dashboard
- ✅ No production surprises
- ✅ You can rebuild any environment from migrations

---

## 📚 Additional Documentation

- `DATABASE_MIGRATION_PROBLEM_AND_SOLUTION.md` - Historical context
- `CURRENT_MIGRATION_STATUS.md` - Status as of 2025-11-09
- `backend/check_schema_consistency.py` - Tool source code
- `backend/scripts/apply_migrations_to_env.py` - Migration script

---

## 🤝 Team Agreement

By following this workflow, we ensure:
1. **No surprises** - Every change is tested first
2. **No data loss** - Migrations are tested before prod
3. **Reproducibility** - Any environment can be rebuilt
4. **Confidence** - We know local == dev == prod

**Everyone on the team commits to:**
- Following this process without shortcuts
- Using the tools provided
- Asking questions if unsure
- Improving this document as we learn

---

**Remember: Discipline now = Confidence later**

When in doubt, run `check_schema_consistency.py`
