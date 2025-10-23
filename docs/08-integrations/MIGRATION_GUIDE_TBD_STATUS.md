# Migration Guide: Add TBD Match Status

**Migration File:** `supabase/migrations/20251019000020_add_tbd_match_status.sql`
**Applies To:** Dev and Production Supabase databases
**Risk Level:** Low (additive change to CHECK constraint)
**Rollback:** Simple (see Rollback section)

## Overview

This migration adds "tbd" (to be determined) to the match_status CHECK constraint, allowing the database to store matches that have been played but scores are not yet available.

## Prerequisites

Before starting:
- ✅ Feature branch merged or ready to deploy
- ✅ Workers will be redeployed after migration
- ✅ Backup of current database (automatic via Supabase)
- ✅ Access to Supabase dashboard or CLI

---

## Option 1: Apply via Supabase CLI (Recommended)

### Step 1: Ensure CLI is Installed

```bash
# Check if Supabase CLI is installed
npx supabase --version

# Expected output: supabase 1.x.x
```

### Step 2: Link to Remote Project (Dev)

```bash
# Navigate to project root
cd /Users/silverbeer/gitrepos/missing-table

# Link to dev project (one-time setup)
npx supabase link --project-ref ppgxasqgqbnauvxozmjw

# You'll be prompted for your Supabase access token
# Get it from: https://app.supabase.com/account/tokens
```

**Expected Output:**
```
✔ Enter your access token: ••••••••
✔ Linked to project "missing-table-dev"
```

### Step 3: Review Migration Before Applying

```bash
# Show the migration SQL
cat supabase/migrations/20251019000020_add_tbd_match_status.sql
```

**Review the contents:**
- ✅ Drops existing CHECK constraint
- ✅ Adds new constraint with 'tbd'
- ✅ Creates index for performance
- ✅ Updates column comments

### Step 4: Apply Migration to Dev

```bash
# Push migrations to dev Supabase
npx supabase db push

# You'll see a diff of changes
```

**Expected Output:**
```
Applying migration 20251019000020_add_tbd_match_status.sql...
✔ Migration applied successfully

Remote database is up to date.
```

### Step 5: Verify Migration Applied

```bash
# Connect to database and verify constraint
npx supabase db remote psql

# In the psql prompt, run:
```

```sql
-- Check the constraint definition
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'matches_match_status_check';

-- Expected output:
-- conname                     | pg_get_constraintdef
-- ---------------------------+----------------------------------------------------
-- matches_match_status_check | CHECK ((match_status IN ('scheduled', 'tbd', 'live', 'completed', 'postponed', 'cancelled')))

-- Exit psql
\q
```

### Step 6: Test with Sample Data

```bash
# Still in psql, insert a test match with tbd status
```

```sql
-- Connect to database
npx supabase db remote psql
```

```sql
-- Insert test match with tbd status
INSERT INTO matches (
    home_team_id,
    away_team_id,
    match_date,
    season,
    match_status
)
SELECT
    (SELECT id FROM teams LIMIT 1 OFFSET 0) as home_team_id,
    (SELECT id FROM teams LIMIT 1 OFFSET 1) as away_team_id,
    CURRENT_DATE as match_date,
    '2024-25' as season,
    'tbd' as match_status;

-- Verify it was inserted
SELECT id, match_status, match_date
FROM matches
WHERE match_status = 'tbd'
ORDER BY created_at DESC
LIMIT 1;

-- Clean up test data
DELETE FROM matches WHERE match_status = 'tbd' AND match_date = CURRENT_DATE;

-- Exit
\q
```

**Expected Output:**
```
INSERT 0 1
 id  | match_status | match_date
-----+--------------+------------
 123 | tbd          | 2025-10-19
(1 row)

DELETE 1
```

---

## Option 2: Apply via Supabase Dashboard (Alternative)

### Step 1: Access SQL Editor

1. Go to https://supabase.com/dashboard
2. Select project: **missing-table-dev** (`ppgxasqgqbnauvxozmjw`)
3. Click **SQL Editor** in left sidebar

### Step 2: Copy Migration SQL

```bash
# Copy the migration contents to clipboard
cat supabase/migrations/20251019000020_add_tbd_match_status.sql | pbcopy
```

Or manually copy the content:

```sql
-- Migration: Add 'tbd' status to match_status CHECK constraint
-- Created: 2025-10-19

-- Step 1: Drop the existing CHECK constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

-- Step 2: Add new CHECK constraint with 'tbd' included
ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'tbd', 'live', 'completed', 'postponed', 'cancelled'));

-- Step 3: Create index for tbd status queries (optional, for performance)
CREATE INDEX IF NOT EXISTS idx_matches_tbd_status
ON matches(match_status)
WHERE match_status = 'tbd';

-- Step 4: Update column comment to document the new status
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled, tbd (match played, score pending), live, completed, postponed, cancelled';

-- Step 5: Add informational comments
COMMENT ON CONSTRAINT matches_match_status_check ON matches IS 'Ensures match_status is one of the valid status values. tbd = match played but score not yet available.';
```

### Step 3: Execute in SQL Editor

1. Paste the SQL into the editor
2. Click **Run** button
3. Check for success message

**Expected Output:**
```
Success. No rows returned.
```

### Step 4: Verify Migration

Run this query in SQL Editor:

```sql
-- Verify constraint
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'matches_match_status_check';

-- Test insert
INSERT INTO matches (
    home_team_id,
    away_team_id,
    match_date,
    season,
    match_status
)
SELECT
    (SELECT id FROM teams LIMIT 1 OFFSET 0),
    (SELECT id FROM teams LIMIT 1 OFFSET 1),
    CURRENT_DATE,
    '2024-25',
    'tbd';

-- Verify
SELECT id, match_status FROM matches WHERE match_status = 'tbd' ORDER BY created_at DESC LIMIT 1;

-- Cleanup
DELETE FROM matches WHERE match_status = 'tbd' AND match_date = CURRENT_DATE;
```

---

## Applying to Production

### ⚠️ Before Production Deployment

1. **Test in dev first** - Ensure dev environment is working
2. **Monitor dev for 24-48 hours** - Check for issues
3. **Coordinate with team** - Announce maintenance window
4. **Backup** - Supabase auto-backups, but verify
5. **Off-peak hours** - Apply during low traffic

### Production Steps (Same as Dev)

```bash
# 1. Link to production project
npx supabase link --project-ref YOUR_PROD_PROJECT_ID

# 2. Apply migration
npx supabase db push

# 3. Verify
npx supabase db remote psql
```

```sql
-- Verify in production
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'matches_match_status_check';

\q
```

---

## Post-Migration Steps

### 1. Deploy Updated Workers

After migration is applied, deploy the updated workers:

```bash
# Rebuild with tbd status support
./k3s/worker/rebuild-and-deploy.sh

# Verify workers are running
kubectl get pods -n match-scraper -l app=missing-table-worker

# Expected: 2/2 Running pods
```

### 2. Monitor Worker Logs

```bash
# Watch for any errors
kubectl logs -n match-scraper -l app=missing-table-worker -f

# Look for:
# ✅ "celery_app_initialized" - Workers started
# ✅ "match_validation_passed" - Messages validated
# ✅ No "Invalid match_status" errors
```

### 3. Test End-to-End

```bash
# Trigger match-scraper (if available)
# Or manually test via RabbitMQ

# Verify workers process tbd status successfully
kubectl logs -n match-scraper -l app=missing-table-worker --tail=100 | grep -i "tbd"
```

### 4. Check Database for TBD Matches

```sql
-- Connect to database
npx supabase db remote psql
```

```sql
-- Query matches with tbd status
SELECT
    id,
    home_team_id,
    away_team_id,
    match_date,
    match_status,
    created_at
FROM matches
WHERE match_status = 'tbd'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Verification Checklist

After migration:

- [ ] Migration applied successfully (no errors)
- [ ] CHECK constraint includes 'tbd'
- [ ] Index created for tbd status
- [ ] Test insert with tbd status works
- [ ] Workers redeployed
- [ ] Workers show no validation errors
- [ ] End-to-end test successful
- [ ] Database contains tbd matches (after scraper runs)

---

## Troubleshooting

### Issue: "constraint matches_match_status_check already exists"

**Solution:**
```sql
-- Drop the constraint first
ALTER TABLE matches DROP CONSTRAINT matches_match_status_check;

-- Then re-run the migration
```

### Issue: "permission denied for table matches"

**Solution:**
- Ensure you're using the service role key (not anon key)
- Check Supabase project settings → API → service_role key

### Issue: Migration shows in CLI but not applied

**Solution:**
```bash
# Force re-sync
npx supabase db reset --linked

# WARNING: This resets the database! Use carefully
# Better option: Apply via SQL Editor manually
```

### Issue: Workers still rejecting tbd status

**Solution:**
```bash
# 1. Verify workers are running latest code
kubectl get pods -n match-scraper -l app=missing-table-worker -o jsonpath='{.items[*].metadata.creationTimestamp}'

# 2. If old timestamps, force rebuild
./k3s/worker/rebuild-and-deploy.sh

# 3. Check logs for validation errors
kubectl logs -n match-scraper -l app=missing-table-worker --tail=200 | grep -i "validation"
```

---

## Rollback Plan

If you need to revert the migration:

### Method 1: SQL Rollback

```sql
-- Remove tbd from constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));

-- Drop tbd index
DROP INDEX IF EXISTS idx_matches_tbd_status;

-- Update comment
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled, live, completed, postponed, cancelled';
```

### Method 2: Update Existing TBD Matches

If you need to rollback but have existing tbd matches:

```sql
-- Convert tbd matches to scheduled
UPDATE matches
SET match_status = 'scheduled'
WHERE match_status = 'tbd';

-- Then apply rollback SQL above
```

### Method 3: Code Rollback

```bash
# Checkout previous version
git checkout main

# Rebuild workers
./k3s/worker/rebuild-and-deploy.sh
```

---

## Timeline Estimate

| Step | Time | Notes |
|------|------|-------|
| Review migration | 5 min | Read SQL, understand changes |
| Apply to dev | 2 min | CLI push or dashboard |
| Verify migration | 5 min | Query constraints, test insert |
| Deploy workers | 3 min | Rebuild and restart |
| Monitor logs | 10 min | Watch for errors |
| End-to-end test | 10 min | Trigger scraper, verify flow |
| **Total (Dev)** | **35 min** | |
| Apply to prod | 2 min | Same as dev |
| Monitor prod | 30 min | Watch first hour closely |
| **Total (Prod)** | **32 min** | |

---

## Support

**Questions?**
- Migration SQL: `supabase/migrations/20251019000020_add_tbd_match_status.sql`
- Implementation docs: `TBD_STATUS_IMPLEMENTATION.md`
- Supabase docs: https://supabase.com/docs/guides/cli/managing-environments

**Logs:**
```bash
# Worker logs
kubectl logs -n match-scraper -l app=missing-table-worker -f

# Database logs
# Available in Supabase dashboard → Logs
```

**Emergency rollback:**
See "Rollback Plan" section above.

---

**Ready to apply?** Start with Option 1 (CLI) for dev environment! ✅
