# Database Migration Best Practices

**Last Updated**: 2026-02-01

## Overview

This document defines the standard practices for managing database schema changes in the Missing Table project. Following these practices ensures consistency, safety, and maintainability of our database schema across all environments.

## Migration Philosophy

- **Single Source of Truth**: All migrations live in `supabase-local/migrations/` (one directory)
- **`supabase/migrations/`** is a symlink to `supabase-local/migrations/` — no more syncing
- **Version Control**: Migrations are tracked in git like any other code
- **Environment Parity**: All environments (local, prod) use the same migrations
- **Safety First**: Always backup before deploying, test locally before cloud
- **No Ad-Hoc SQL**: Schema changes outside of migrations are forbidden

## Directory Structure

```
supabase-local/
├── migrations/                              # THE single source of truth
│   ├── 00000000000000_schema.sql            # Consolidated baseline (pg_dump of full schema)
│   ├── 20260201000000_add_new_feature.sql   # New migrations go alongside baseline
│   └── .archive/                            # Historical migration filenames (reference only)
├── supabase/
│   ├── config.toml                          # Supabase CLI configuration
│   ├── seed.sql                             # Reference data (age_groups, seasons, etc.)
│   └── migrations -> ../migrations          # Symlink for Supabase CLI
└── config.toml                              # Git-tracked copy of config

supabase/
└── migrations -> ../supabase-local/migrations  # Symlink — one source of truth

scripts/
├── setup-local-db.sh                        # One-command local DB setup
├── seed_test_users.sh                       # Create test users
├── db_tools.sh                              # Backup/restore utility
└── test-data/                               # Test data scripts
```

## Migration Naming Convention

**Format**: `YYYYMMDDHHMMSS_description.sql`

**Examples**:
- `20251028120000_add_player_stats_table.sql`
- `20251029090000_add_team_logo_field.sql`
- `20251030153000_add_match_attendance.sql`

**Rules**:
- Timestamp must be unique and chronological
- Description should be lowercase with underscores
- Description should briefly describe what the migration does
- Use present tense verbs: `add`, `update`, `fix`, `create`, `drop`, `rename`

## Creating New Migrations

### Method 1: Using Supabase DB Diff (Recommended)

This method automatically generates migration SQL by comparing your local database to the schema.

```bash
# 1. Make changes in Supabase Studio (http://localhost:54323)
#    - Create/modify tables
#    - Add/remove columns
#    - Update indexes, constraints, etc.

# 2. Generate migration from changes
cd supabase-local
npx supabase db diff -f add_new_feature

# 3. Review the generated migration
cat supabase/migrations/[timestamp]_add_new_feature.sql

# 4. Test locally
npx supabase db reset

# 5. Commit to git (symlink means only one directory to track)
git add supabase-local/migrations/
git commit -m "feat: add new feature migration"
```

### Method 2: Manual SQL Migration

For complex migrations or when you prefer to write SQL directly.

```bash
# 1. Create new migration file
cd supabase-local
npx supabase migration new add_new_feature

# This creates: migrations/[timestamp]_add_new_feature.sql

# 2. Edit the migration file
vim migrations/[timestamp]_add_new_feature.sql

# 3. Write your SQL (see SQL Best Practices below)

# 4. Test locally
npx supabase db reset

# 5. Commit to git
git add supabase-local/migrations/
git commit -m "feat: add new feature migration"
```

## Migration SQL Best Practices

### Make Migrations Idempotent

Migrations should be safe to run multiple times:

```sql
-- ✅ GOOD: Uses IF NOT EXISTS
CREATE TABLE IF NOT EXISTS player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0
);

-- ✅ GOOD: Check before adding column
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='teams' AND column_name='logo_url'
    ) THEN
        ALTER TABLE teams ADD COLUMN logo_url TEXT;
    END IF;
END $$;

-- ❌ BAD: Will fail if table exists
CREATE TABLE player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL
);
```

### Add Comprehensive Comments

```sql
-- ============================================================================
-- ADD PLAYER STATISTICS TRACKING
-- ============================================================================
-- Purpose: Track individual player statistics for matches
-- Author: Tom Drake
-- Date: 2025-10-28
-- Related: Issue #123
--
-- Tables:
-- - player_stats: New table for player statistics
-- - players: New table for player information
--
-- Impact:
-- - No breaking changes
-- - Adds 2 new tables
-- - Adds foreign key constraints
-- ============================================================================

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    jersey_number INTEGER,
    position VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Player statistics table
CREATE TABLE IF NOT EXISTS player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    yellow_cards INTEGER DEFAULT 0,
    red_cards INTEGER DEFAULT 0,
    minutes_played INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, match_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_stats_match ON player_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
```

### Use Transactions When Appropriate

```sql
-- ============================================================================
-- RENAME TABLES AND UPDATE REFERENCES
-- ============================================================================
-- This migration renames tables and updates all references atomically

BEGIN;

-- Rename tables
ALTER TABLE old_table_name RENAME TO new_table_name;

-- Update foreign keys
ALTER TABLE related_table
    DROP CONSTRAINT fk_old_name,
    ADD CONSTRAINT fk_new_name
        FOREIGN KEY (new_table_id) REFERENCES new_table_name(id);

-- Update indexes
ALTER INDEX idx_old_name RENAME TO idx_new_name;

COMMIT;
```

### Handle Data Migrations Carefully

```sql
-- ============================================================================
-- MIGRATE DATA TO NEW STRUCTURE
-- ============================================================================

-- Add new column
ALTER TABLE teams ADD COLUMN IF NOT EXISTS full_name TEXT;

-- Migrate existing data
UPDATE teams
SET full_name = CONCAT(name, ' ', city)
WHERE full_name IS NULL;

-- Make column NOT NULL after data migration
ALTER TABLE teams ALTER COLUMN full_name SET NOT NULL;
```

## Migration Deployment Workflow

### 1. Local Testing (REQUIRED)

```bash
# Switch to local environment
./switch-env.sh local

# Start local Supabase
cd supabase-local && npx supabase start

# Reset database with all migrations
npx supabase db reset

# Restore production-like data
cd .. && ./scripts/db_tools.sh restore

# Start application and test
./missing-table.sh dev

# Run tests
cd backend && uv run pytest

# Verify changes work as expected
```

### 2. Production Deployment

**⚠️ CRITICAL: Only deploy to production during scheduled maintenance windows**

```bash
# 1. Announce deployment window to team

# 2. Create production backup
./switch-env.sh prod
./scripts/db_tools.sh backup prod

# 3. Apply migrations
cd supabase-local && npx supabase db push --linked

# 4. Verify migration applied
npx supabase migration list

# 5. Smoke test production
./scripts/health-check.sh prod

# 6. Monitor for 15 minutes
watch -n 30 'curl -s https://missingtable.com/api/health'

# 7. Check application logs
kubectl logs -l app=missing-table-backend -n missing-table --tail=100

# 8. Announce deployment complete
```

## Rollback Strategy

### If Migration Fails During Application

```bash
# 1. Check error logs
npx supabase db push --debug

# 2. Fix the migration SQL
vim supabase/migrations/[timestamp]_problematic_migration.sql

# 3. Test fix locally
cd supabase-local && npx supabase db reset

# 4. Re-apply to affected environment
npx supabase db push --linked
```

### If Migration Succeeds But Breaks Application

**Option A: Fix Forward (Preferred)**

```bash
# 1. Create hotfix migration
cd supabase-local
npx supabase migration new hotfix_issue_description

# 2. Write fix
vim migrations/[timestamp]_hotfix_issue_description.sql

# 3. Test locally, then deploy
npx supabase db reset
# ... test ...
npx supabase db push --linked
```

**Option B: Rollback Migration (Use Sparingly)**

```bash
# 1. Create rollback migration
cd supabase-local
npx supabase migration new rollback_problematic_feature

# 2. Write reverse migration
# Example: If original added a table, DROP the table
# Example: If original added a column, remove the column

# 3. Test locally, then deploy
npx supabase db reset
# ... test ...
npx supabase db push --linked
```

## Migration Checklist

Before committing a migration, verify:

- [ ] Migration file follows naming convention
- [ ] Migration is idempotent (safe to run multiple times)
- [ ] Migration includes comprehensive comments
- [ ] Migration tested locally successfully
- [ ] Data restore works after migration
- [ ] Application starts and works with new schema
- [ ] Tests pass with new schema
- [ ] Migration added to `supabase-local/migrations/` (single source of truth)
- [ ] Breaking changes documented in commit message
- [ ] Team notified if migration requires downtime

## Common Migration Patterns

### Adding a New Table

```sql
CREATE TABLE IF NOT EXISTS new_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    foreign_key_id INTEGER REFERENCES other_table(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_new_table_foreign_key ON new_table(foreign_key_id);

-- RLS Policies
ALTER TABLE new_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY new_table_select_all ON new_table
    FOR SELECT USING (true);

CREATE POLICY new_table_admin_all ON new_table
    FOR ALL USING (is_admin());
```

### Adding a Column

```sql
-- Add column (nullable initially for existing data)
ALTER TABLE teams ADD COLUMN IF NOT EXISTS logo_url TEXT;

-- Optionally add default or migrate data
UPDATE teams SET logo_url = 'https://example.com/default-logo.png'
WHERE logo_url IS NULL;

-- Optionally make NOT NULL after data migration
-- ALTER TABLE teams ALTER COLUMN logo_url SET NOT NULL;
```

### Renaming a Table

```sql
-- Rename table
ALTER TABLE IF EXISTS old_name RENAME TO new_name;

-- Update sequence if it exists
ALTER SEQUENCE IF EXISTS old_name_id_seq RENAME TO new_name_id_seq;

-- Rename indexes
ALTER INDEX IF EXISTS idx_old_name_column RENAME TO idx_new_name_column;

-- Rename RLS policies
ALTER POLICY old_name_select_all ON new_name RENAME TO new_name_select_all;
```

### Adding an Enum Value

```sql
-- Add new enum value (safe, doesn't block reads)
ALTER TYPE match_status ADD VALUE IF NOT EXISTS 'forfeited';

-- NOTE: Cannot remove enum values easily - plan carefully!
```

## What NOT To Do

### Never Modify Existing Migrations

Once a migration is deployed to any environment, it is **immutable**.

```bash
# ❌ BAD: Editing deployed migration
vim supabase/migrations/20251028000001_baseline_schema.sql

# ✅ GOOD: Create new migration
npx supabase migration new fix_issue
```

### Never Run Ad-Hoc SQL in Production

```bash
# ❌ BAD: Direct SQL execution
psql -h prod-db.supabase.co -c "ALTER TABLE teams ADD COLUMN logo TEXT;"

# ✅ GOOD: Create migration and deploy properly
npx supabase migration new add_team_logo
# ... edit migration ...
npx supabase db push --linked
```

### Never Skip Local Testing

```bash
# ❌ BAD: Deploy directly to prod
git commit -m "add migration" && git push
kubectl rollout restart deployment/backend -n missing-table

# ✅ GOOD: Test locally first
npx supabase db reset
./scripts/db_tools.sh restore
# ... verify everything works ...
# Then deploy
```

### Never Use DROP Without Backup

```bash
# ❌ BAD: Drop without backup
DROP TABLE old_unused_table;

# ✅ GOOD: Backup first
-- 1. Backup production
./scripts/db_tools.sh backup prod

-- 2. Mark as deprecated in migration comments
-- /*
-- DEPRECATED TABLE: old_unused_table
-- Safe to drop after 2025-11-30
-- Backup: database_backup_20251028_114218.json
-- */

-- 3. Drop after waiting period
-- DROP TABLE IF EXISTS old_unused_table;
```

## Troubleshooting

### Migration Not Applying

```bash
# Check migration history
npx supabase migration list

# Check for syntax errors
npx supabase db push --debug

# Verify migration file name format
ls -la supabase-local/migrations/
```

### Schema Drift Detected

```bash
# Generate diff to see what's different
cd supabase-local
npx supabase db diff

# Either:
# Option A: Create migration for manual changes
npx supabase db diff -f capture_manual_changes

# Option B: Reset to match migrations (DESTRUCTIVE)
npx supabase db reset
```

### PostgREST Not Seeing New Tables

```bash
# Restart PostgREST to reload schema cache
docker restart supabase_rest_supabase-local

# Or restart entire Supabase stack
cd supabase-local
npx supabase stop
npx supabase start
```

## Schema Version Tracking

### Overview

The database includes explicit schema version tracking via the `schema_version` table. This allows you to:
- Know exactly which schema version is deployed in each environment
- Perform runtime version checks in application code
- Track migration history and audit trail
- Verify environment configurations

### Checking Schema Version

**Query current version:**
```sql
SELECT * FROM get_schema_version();
-- Returns: version, applied_at, description
```

**View all version history:**
```sql
SELECT * FROM schema_version ORDER BY applied_at DESC;
```

**From application code (Python example):**
```python
from dao.supabase_data_access import SupabaseDataAccess

dao = SupabaseDataAccess()
result = dao.supabase.rpc('get_schema_version').execute()
current_version = result.data[0]['version']
print(f"Schema version: {current_version}")
```

### Adding Versions in Future Migrations

When you create a new migration that changes the schema, add a version entry:

```sql
-- At the end of your migration file
SELECT add_schema_version(
    '1.1.0',
    '20251029000002_add_player_stats',
    'Added player statistics tracking tables'
);
```

### Semantic Versioning

Use **MAJOR.MINOR.PATCH** format (e.g., `1.0.0`):

- **MAJOR**: Breaking changes (rare, coordinate with team)
  - Example: `2.0.0` - Renamed core tables
- **MINOR**: New features (backward compatible)
  - Example: `1.1.0` - Added player_stats table
- **PATCH**: Bug fixes, small changes (backward compatible)
  - Example: `1.1.1` - Fixed index on player_stats

**Examples:**
- `1.0.0` - Initial baseline (current)
- `1.1.0` - Add player statistics feature
- `1.1.1` - Fix player statistics index
- `1.2.0` - Add match attendance tracking
- `2.0.0` - Major refactor (breaking change)

### Version Table Schema

```sql
CREATE TABLE schema_version (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    migration_name VARCHAR(255) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(100) DEFAULT CURRENT_USER
);
```

## Baseline Schema

### What Is It?

The baseline migration (`00000000000000_schema.sql`) is a `pg_dump --schema-only` of the complete public schema. It consolidates all historical migrations into a single file. This provides:

- Clean starting point for new environments
- Complete schema in one place
- Faster database resets
- Simpler onboarding for new developers

### Seed Data

Reference data is seeded via `supabase-local/supabase/seed.sql` (enabled in config.toml). This includes:
- Age groups (U13-U19)
- Seasons (2023-2024 through 2025-2026)
- Match types (League, Tournament, Friendly, Playoff)
- Leagues (Homegrown, Academy)
- Divisions (Northeast, New England)

### One-Command Setup

```bash
# Full setup: schema + seed + test users
./scripts/setup-local-db.sh

# With match/team data restore
./scripts/setup-local-db.sh --restore
```

### Baseline Contents

The baseline includes:
- All tables (age_groups, seasons, teams, matches, clubs, players, etc.)
- Auth system (user_profiles, invitations, invite_requests, team_manager_assignments)
- Reference tables (divisions, match_types, team_match_types, leagues)
- Enums (match_status, invite_request_status)
- Functions (is_admin, is_team_manager, manages_team, reset_all_sequences, etc.)
- RLS policies for all tables (51 policies)
- Indexes for performance
- Constraints for data integrity

### After Baseline

New migrations are incremental changes on top of the baseline:
- `00000000000000_schema.sql` (baseline)
- `20260201000000_add_player_stats.sql` (new feature)
- `20260202000000_add_match_attendance.sql` (new feature)

### Re-consolidating the Baseline

Periodically, you may want to re-consolidate the baseline by dumping the current schema:

```bash
PGPASSWORD=postgres pg_dump --schema-only --no-owner --no-privileges \
  -h 127.0.0.1 -p 54332 -U postgres -d postgres --schema=public \
  > supabase-local/migrations/00000000000000_schema.sql
# Then remove the \restrict/\unrestrict lines and CREATE SCHEMA public
```

## Resources

- **Supabase CLI Documentation**: https://supabase.com/docs/guides/cli
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Project Migrations**: `/supabase-local/migrations/`

## Questions?

If you're unsure about a migration:
1. Ask in the team chat
2. Test extensively in local environment
3. When in doubt, make it idempotent and reversible

---

**Remember**: Good migrations are boring. The goal is safe, predictable schema changes that never surprise anyone.
