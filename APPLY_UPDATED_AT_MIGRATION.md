# Quick Start: Apply Updated_At Trigger Migration

**Migration:** 021_add_updated_at_trigger.sql
**Time Required:** ~5 minutes per environment
**Risk:** Very Low (additive change, no data modification)
**Rollback:** Simple (see bottom)

---

## 📝 What This Does

- Adds automatic `updated_at` timestamp updates for the `matches` table
- Fixes `match_status` constraint to allow 'tbd' and 'completed' statuses
- **No code changes required** - works at database level
- **Zero downtime** - non-breaking change

---

## 🔧 Apply to All Environments

### 1️⃣ Local Database

#### Option A: Supabase Dashboard (Easiest)
```bash
# 1. Copy the migration SQL
cat backend/sql/021_add_updated_at_trigger.sql

# 2. Go to https://supabase.com/dashboard
# 3. Select your LOCAL project
# 4. Go to SQL Editor → New Query
# 5. Paste the SQL
# 6. Click Run
# ✅ Expected: "Success. No rows returned."
```

#### Option B: Direct psql (if you have connection string)
```bash
cd /Users/silverbeer/gitrepos/missing-table

# Make sure DATABASE_URL is set in backend/.env.local
psql $(grep DATABASE_URL backend/.env.local | cut -d= -f2-) < backend/sql/021_add_updated_at_trigger.sql

# ✅ Expected: CREATE EXTENSION, ALTER TABLE, CREATE TRIGGER, COMMENT
```

#### Option C: Python Script
```bash
cd /Users/silverbeer/gitrepos/missing-table/backend

# Apply to local
python scripts/apply_migrations_to_env.py --env local

# ✅ Expected: Migration applied successfully
```

---

### 2️⃣ Dev Database

#### Recommended: Supabase Dashboard
```bash
# 1. Copy the migration SQL
cat backend/sql/021_add_updated_at_trigger.sql

# 2. Go to https://supabase.com/dashboard
# 3. Select your DEV project
# 4. Go to SQL Editor → New Query
# 5. Paste the SQL
# 6. Click Run
# ✅ Expected: "Success. No rows returned."
```

#### Alternative: Python Script
```bash
cd /Users/silverbeer/gitrepos/missing-table/backend

# Apply to dev
python scripts/apply_migrations_to_env.py --env dev

# ✅ Expected: Migration applied successfully
```

---

### 3️⃣ Production Database

**⚠️ Important: Only apply after testing in dev for 24+ hours**

#### Recommended: Supabase Dashboard (for safety)
```bash
# 1. Copy the migration SQL
cat backend/sql/021_add_updated_at_trigger.sql

# 2. Go to https://supabase.com/dashboard
# 3. Select your PROD project
# 4. Go to SQL Editor → New Query
# 5. Paste the SQL
# 6. Click Run
# ✅ Expected: "Success. No rows returned."
```

#### Alternative: Python Script (SSL)
```bash
cd /Users/silverbeer/gitrepos/missing-table/backend

# Dry run first!
python scripts/apply_migrations_prod_ssl.py --dry-run

# If dry run looks good:
python scripts/apply_migrations_prod_ssl.py

# ✅ Expected: Migration applied successfully
```

---

## ✅ Verify Migration Applied

Run this SQL in Supabase Dashboard SQL Editor for each environment:

```sql
-- 1. Check trigger exists
SELECT
  trigger_name,
  event_manipulation,
  event_object_table
FROM information_schema.triggers
WHERE trigger_name = 'handle_updated_at';

-- Expected: 1 row with UPDATE on matches table

-- 2. Check match_status constraint updated
SELECT pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'matches_match_status_check';

-- Expected: Should include 'tbd' and 'completed'

-- 3. Test the trigger (optional)
-- Pick any match ID from your database
UPDATE matches
SET home_score = home_score
WHERE id = 594;  -- Change to a real match ID

-- Check updated_at changed
SELECT id, home_score, updated_at
FROM matches
WHERE id = 594;

-- ✅ updated_at should be current timestamp!
```

---

## 🎯 Expected Behavior After Migration

### Immediate:
- ✅ All future match updates will automatically update `updated_at`
- ✅ Celery workers can use 'tbd' and 'completed' statuses without errors
- ✅ No application restarts needed

### Next Scraper Run (6 AM UTC):
- ✅ Match scores will update AND `updated_at` will update
- ✅ UI will show correct "Last Updated" timestamps
- ✅ Example: Match 99479 will show current date when scores change

---

## 📊 Monitor After Applying

### Check Celery Worker Logs (K3s)
```bash
# Check for any errors
kubectl logs -n match-scraper -l app=missing-table-celery-worker-prod --tail=100

# Should NOT see:
# ❌ "violates check constraint matches_match_status_check"

# Should see (after next scraper run):
# ✅ "Successfully updated match 594: {'home_score': 1, 'away_score': 4, 'match_status': 'completed'}"
```

### Check UI
1. Find a match that updated recently
2. Verify "Last Updated" shows recent timestamp
3. Compare with "Created" timestamp - should be different

---

## 🔄 Rollback (If Needed)

If you need to rollback this migration, run this SQL:

```sql
-- Remove the trigger
DROP TRIGGER IF EXISTS handle_updated_at ON matches;

-- Restore old constraint (without tbd/completed)
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'played', 'postponed', 'cancelled'));

-- Note: You can keep moddatetime extension enabled, it doesn't hurt
```

---

## 📚 Additional Documentation

- **Full details:** `backend/docs/021_APPLY_MIGRATION.md`
- **Migration SQL:** `backend/sql/021_add_updated_at_trigger.sql`
- **Also stored in:** `backend/supabase/migrations/021_add_updated_at_trigger.sql` (local only)

---

## ✨ Summary Checklist

- [ ] Local: Migration applied and verified
- [ ] Dev: Migration applied and verified
- [ ] Dev: Monitor for 24-48 hours
- [ ] Production: Migration applied and verified
- [ ] Production: Monitor for first few hours
- [ ] Confirm next scraper run updates timestamps correctly

---

**Ready? Start with Local → Dev → (wait 24h) → Prod** ⬆️
