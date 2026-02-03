# Schema Sync Tooling

This directory contains tooling for syncing database schemas between environments (local and prod).

## Overview

When the production database schema evolves (new columns, indexes, constraints), the local environment may fall out of sync. These tools help keep local and prod schemas aligned.

## Tools

### 1. Schema Sync Scripts

**Location:**
- `scripts/sync_local_schema.sql` - SQL migration for adding missing columns
- `backend/sync_local_schema.py` - Python script to execute the migration

**Purpose:** Adds missing scraper integration fields to the matches table:
- `mls_match_id` - MLS Next match identifier
- `data_source` - Source of match data (manual or mls_scraper)
- `last_scraped_at` - Timestamp when scraper last updated
- `score_locked` - Prevents scraper from overwriting manual scores
- `created_by` - User who created the match
- `updated_by` - User who last updated the match
- `source` - Source of match data (manual or match-scraper)

**Usage:**
```bash
# From backend directory
cd backend
uv run python sync_local_schema.py
```

**Output:**
```
🔄 Syncing local schema with prod...
📝 Connecting to database...
📝 Executing schema migration SQL...
✅ Schema migration completed successfully!

📋 Verified new columns in matches table:
   ✓ created_by (uuid)
   ✓ data_source (character varying)
   ✓ last_scraped_at (timestamp with time zone)
   ✓ mls_match_id (bigint)
   ✓ score_locked (boolean)
   ✓ source (character varying)
   ✓ updated_by (uuid)
```

## How to Verify Schema Sync

### Check Database Schema

```bash
# Switch to local environment
./switch-env.sh local

# Check database stats
cd backend
uv run python inspect_db.py stats
```

### Check API Schema

```bash
# Compare prod vs local API schemas
curl -s "https://missingtable.com/api/matches?limit=1" | \
  python3 -c "import sys, json; print(sorted(json.load(sys.stdin)[0].keys()))"

curl -s "http://localhost:8080/api/matches?limit=1" | \
  python3 -c "import sys, json; print(sorted(json.load(sys.stdin)[0].keys()))"
```

Both should return identical column lists.

## When to Use

Use these tools when:
1. **After applying new migrations to prod** - Sync local to match
2. **Local database is rebuilt** - Restore schema compatibility
3. **Schema drift detected** - Bring environments back in sync

## Related Documentation

- [Database Backup and Restore](../CLAUDE.md#database-management-workflow)
- [Environment Management](../docs/02-development/environment-management.md)
- [Supabase Migrations](../supabase/migrations/README.md)

## Notes

- The Python script requires `psycopg2` dependency (included in backend requirements)
- Requires local environment credentials in `backend/.env.local`
- Uses transactions - rolls back on error
- Idempotent - safe to run multiple times (uses `IF NOT EXISTS`)

## Created

- **Date:** 2025-10-24
- **Purpose:** Sync match-scraper integration fields to local environment
- **Related Issue:** Local database was missing 7 columns that production had
