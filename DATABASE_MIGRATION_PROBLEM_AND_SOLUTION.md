# Database Migration Problem & Solution

## Current State (The Mess)

### ❌ Problems Identified

1. **Multiple Migration Directories** (3 different locations!)
   - `backend/supabase/migrations/` - 16 files (gitignored)
   - `supabase-local/migrations/` - 9 files
   - `supabase/migrations/` - 8 files

2. **Databases Are Out of Sync** (verified by `check_schema_consistency.py`)
   - Local has **7 migrations** applied
   - Dev has **4 migrations** applied
   - Different column types on `matches` table:
     - `match_status`: LOCAL = ENUM, DEV = VARCHAR
     - `match_id`: LOCAL = VARCHAR, DEV = TEXT
     - `mls_match_id`: LOCAL = VARCHAR, DEV = BIGINT
   - Missing tables: `team_aliases` exists in dev but not local
   - Missing triggers: 3 triggers in dev missing from local

3. **No Clear Migration Process**
   - Multiple scripts: `apply_migrations_to_env.py`, `apply_migrations_prod_ssl.py`, `apply_migrations_local.py`
   - Scripts point to different migration directories
   - Ad-hoc migrations applied manually via Supabase Dashboard

### 🔍 Root Cause

The project has **evolved through multiple migration strategies** without consolidating:
- Started with manual SQL scripts
- Tried Supabase CLI migrations (supabase/migrations/)
- Added custom Python migration system (supabase-local/migrations/)
- Individual migrations applied out of order

---

## ✅ Recommended Solution

### Option 1: Supabase CLI (Recommended for Supabase projects)

**Pros:**
- Official Supabase tool
- Automatic tracking in `supabase_migrations` table
- Works with all Supabase features
- Can generate migrations from DB diff
- Migration history in git

**Cons:**
- Requires npx/Supabase CLI installed
- Learning curve
- Some migrations might be gitignored (can fix)

**Implementation:**

1. **Choose ONE source of truth**: `supabase/migrations/`

2. **Clear gitignore** to allow tracking migrations:
   ```bash
   # In .gitignore, change:
   # supabase/
   # To be more specific:
   supabase/.branches/
   supabase/.temp/
   ```

3. **Generate current schema baseline:**
   ```bash
   cd supabase
   npx supabase db diff --schema public > migrations/$(date +%Y%m%d%H%M%S)_baseline_current_state.sql
   ```

4. **Standard workflow:**
   ```bash
   # Make schema changes in Supabase Dashboard (dev environment)

   # Generate migration from diff
   npx supabase db diff --linked --schema public > migrations/new_migration.sql

   # Apply to other environments
   npx supabase db push --linked  # for dev
   npx supabase db push --db-url postgresql://...  # for local/prod
   ```

---

### Option 2: Custom Python System (Current approach, needs cleanup)

**Pros:**
- Full control
- Can customize for specific needs
- Already partially implemented

**Cons:**
- More maintenance
- Need to ensure consistency
- Reinventing the wheel

**Implementation:**

1. **Consolidate to ONE migration directory**: `supabase-local/migrations/`

2. **Create master sync script**:
   ```bash
   # backend/sync_all_databases.py
   - Reads all .sql files from supabase-local/migrations/
   - Checks schema_version table in each environment
   - Applies missing migrations in order
   - Verifies schema consistency after
   ```

3. **Standard workflow:**
   ```bash
   # 1. Create migration file
   backend/supabase-local/migrations/YYYYMMDDHHMMSS_description.sql

   # 2. Apply to all environments
   cd backend
   python sync_all_databases.py --check  # dry run
   python sync_all_databases.py --apply  # apply

   # 3. Verify
   python check_schema_consistency.py
   ```

---

## 🚀 Immediate Action Plan

### Phase 1: Establish Baseline (Do This First!)

```bash
# 1. Check current state
cd /Users/silverbeer/gitrepos/missing-table/backend
uv run python check_schema_consistency.py > schema_report_$(date +%Y%m%d).txt

# 2. Choose DEV as source of truth (it's your production-like environment)
# Export dev schema
pg_dump --schema-only $(grep DATABASE_URL .env.dev | cut -d= -f2) > dev_schema_baseline.sql

# 3. Apply dev schema to local to sync them
# DANGER: This will DROP local database!
psql $(grep DATABASE_URL .env.local | cut -d= -f2) -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql $(grep DATABASE_URL .env.local | cut -d= -f2) < dev_schema_baseline.sql

# 4. Verify they match
uv run python check_schema_consistency.py
```

### Phase 2: Choose Migration System

**Decision Matrix:**

| Criteria | Supabase CLI | Custom Python |
|----------|--------------|---------------|
| Ease of use | ✅ Easy | ⚠️ Medium |
| Supabase features | ✅ Full support | ⚠️ Manual |
| Control | ⚠️ Less | ✅ Full |
| Maintenance | ✅ Low | ❌ High |
| Team familiarity | ? | ✅ Python |

**Recommendation: Supabase CLI** (you're using Supabase, use their tools)

### Phase 3: Going Forward

1. **Document the process** (I'll create this)
2. **Add pre-commit hooks** to prevent manual schema changes
3. **Always verify** with `check_schema_consistency.py` after migrations
4. **Never apply migrations manually** via Supabase Dashboard (use CLI/scripts)

---

## 📋 Quick Start: Sync Databases NOW

### Conservative Approach (No Data Loss)

```bash
cd /Users/silverbeer/gitrepos/missing-table/backend

# 1. Check what's different
uv run python check_schema_consistency.py

# 2. For now, apply the updated_at trigger we just created to ensure that's consistent
uv run python apply_021_migration.py --env local  # Already done
uv run python apply_021_migration.py --env dev    # Already done

# 3. For the other differences, we need to decide:
#    - Do we want local to match dev?
#    - Or dev to match local?
#
# RECOMMENDATION: Make local match dev (dev is closer to prod)
```

### The Nuclear Option (Fresh Start - Data Loss!)

**Only if you don't care about local data:**

```bash
cd /Users/silverbeer/gitrepos/missing-table/backend

# Export dev schema
pg_dump --schema-only $(grep DATABASE_URL .env.dev | cut -d= -f2-) > /tmp/dev_schema.sql

# Nuke and recreate local
psql $(grep DATABASE_URL .env.local | cut -d= -f2-) << 'EOF'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
EOF

# Apply dev schema to local
psql $(grep DATABASE_URL .env.local | cut -d= -f2-) < /tmp/dev_schema.sql

# Verify
uv run python check_schema_consistency.py
```

---

## 🎯 Next Steps (After Syncing)

1. **Delete unused migration directories**
   ```bash
   rm -rf backend/supabase/  # These are gitignored anyway
   # Keep either supabase/ or supabase-local/, not both
   ```

2. **Update .gitignore** to track migrations
   ```
   # Allow migrations to be tracked
   !supabase/migrations/
   ```

3. **Create standard operating procedure** document

4. **Add CI check** that verifies schema consistency in PRs

---

## 🤔 Questions for You

1. **Do you want to use Supabase CLI or custom Python approach?**
   - I recommend Supabase CLI

2. **Is your local database data important?**
   - If not, we can nuke and sync from dev
   - If yes, we need to write careful migrations

3. **Which environment is the "truth"?**
   - Seems like dev is closest to what you want
   - We should sync local to dev

4. **Do you want me to:**
   - Write the complete migration system?
   - Just fix the immediate sync issue?
   - Create documentation and let you implement?

---

## 📁 New Files Created

1. **check_schema_consistency.py** - Verifies all environments match
2. **apply_021_migration.py** - Applies single migration (template for others)
3. This document - Explains the problem and solutions

**Run this to see current state:**
```bash
cd /Users/silverbeer/gitrepos/missing-table/backend
uv run python check_schema_consistency.py
```
