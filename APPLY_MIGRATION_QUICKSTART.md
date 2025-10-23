# Quick Start: Apply TBD Status Migration

**Time Required:** ~10 minutes
**Risk:** Low (additive change)
**Rollback:** Simple

---

## 🚀 Fast Track (Dev Environment)

### 1️⃣ Apply Migration (Choose One Method)

#### Method A: Supabase CLI (Recommended)

```bash
# Navigate to project
cd /Users/silverbeer/gitrepos/missing-table

# Apply migration
npx supabase db push

# ✅ Expected: "Migration applied successfully"
```

#### Method B: Supabase Dashboard

1. Go to https://supabase.com/dashboard
2. Select project: **missing-table-dev**
3. Click **SQL Editor**
4. Paste migration SQL:

```bash
cat supabase/migrations/20251019000020_add_tbd_match_status.sql
```

5. Click **Run**
6. ✅ Expected: "Success. No rows returned."

---

### 2️⃣ Verify Migration

```bash
# Quick verification
npx supabase db remote psql
```

```sql
-- Check constraint (should include 'tbd')
SELECT pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conname = 'matches_match_status_check';

-- Expected output contains: 'tbd'

\q
```

---

### 3️⃣ Deploy Updated Workers

```bash
# Rebuild and deploy
./k3s/worker/rebuild-and-deploy.sh

# Verify pods are running
kubectl get pods -n match-scraper -l app=missing-table-worker

# Expected: 2/2 pods READY
```

---

### 4️⃣ Verify End-to-End

```bash
# Watch worker logs
kubectl logs -n match-scraper -l app=missing-table-worker -f

# Look for:
# ✅ "celery_app_initialized"
# ✅ No "Invalid match_status" errors
```

---

## ✅ Success Indicators

- Migration applied without errors
- Workers show 2/2 READY
- No validation errors in logs
- Test message with tbd status processes successfully

---

## 🔴 If Something Goes Wrong

### Rollback Migration

```bash
npx supabase db remote psql
```

```sql
ALTER TABLE matches DROP CONSTRAINT matches_match_status_check;
ALTER TABLE matches ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));
\q
```

### Rollback Workers

```bash
git checkout main
./k3s/worker/rebuild-and-deploy.sh
```

---

## 📚 Full Documentation

- **Detailed guide:** `docs/08-integrations/MIGRATION_GUIDE_TBD_STATUS.md`
- **Implementation:** `TBD_STATUS_IMPLEMENTATION.md`

---

## 🎯 Production Deployment

**Only after dev is stable for 24-48 hours:**

```bash
# Link to production
npx supabase link --project-ref YOUR_PROD_PROJECT_ID

# Apply migration (same command)
npx supabase db push

# Deploy workers (same command)
./k3s/worker/rebuild-and-deploy.sh

# Monitor closely for first hour
kubectl logs -n match-scraper -l app=missing-table-worker -f
```

---

**Ready? Run commands above in order!** ⬆️
