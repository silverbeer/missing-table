# Database Operations

> **Audience**: Developers
> **Prerequisites**: Local Supabase running (`cd supabase-local && npx supabase start`)

Overview of database management for the Missing Table project.

---

## Quick Reference

```bash
# Full local DB setup from scratch (schema + seed + test users)
./scripts/setup-local-db.sh              # Without match data
./scripts/setup-local-db.sh --restore    # With match data from existing backup
./scripts/setup-local-db.sh --from-prod  # Backup from prod first, then restore locally

# Backup/Restore
./scripts/db_tools.sh backup             # Create backup from current environment
APP_ENV=prod ./scripts/db_tools.sh backup  # Create backup from production
./scripts/db_tools.sh restore            # Restore from latest backup
./scripts/db_tools.sh list               # List available backups

# Reset database (applies schema + seed, then restores data)
./scripts/db_tools.sh reset              # Requires a backup less than 4 hours old

# Local Supabase
cd supabase-local && npx supabase start|stop|status

# Reset schema only (no data restore)
cd supabase-local && npx supabase db reset
```

---

## Key Concepts

### Backup Freshness Guard

The `db_tools.sh reset` command includes a **4-hour safety guard**: it will refuse to reset the database unless a backup exists that is less than 4 hours old. This prevents accidental data loss from stale backups. If your latest backup is older than 4 hours, create a fresh one first:

```bash
./scripts/db_tools.sh backup
./scripts/db_tools.sh reset
```

### Schema vs Data

- **Schema** is managed through migrations in `supabase-local/migrations/`
- **Seed data** (reference tables) lives in `supabase-local/supabase/seed.sql`
- **Application data** (teams, matches) is managed via backup/restore

---

## Detailed Guides

| Topic | Guide |
|-------|-------|
| **Schema migrations** | [Schema Migrations](schema-migrations.md) — creating, testing, and deploying migrations |
| **Backup & restore** | [Database Backup](../07-operations/database-backup.md) — backup system, restore procedures, file format |

---

## Common Workflows

### Starting Fresh (from existing backup)

```bash
./scripts/setup-local-db.sh --restore
```

This runs `supabase db reset` (schema + seed), creates test users, and restores match data from the latest backup.

### Refresh Local from Production

```bash
./scripts/setup-local-db.sh --from-prod
```

This is the **recommended workflow** for syncing your local database with production. It:
1. Creates a fresh backup from prod
2. Resets local database (schema + seed)
3. Restores match/team data from the fresh backup
4. Flushes Redis cache
5. Seeds test users

### After Schema Changes

```bash
./scripts/db_tools.sh backup          # Safety backup first
cd supabase-local && npx supabase db reset
cd .. && ./scripts/db_tools.sh restore
```

### Creating a New Migration

```bash
cd supabase-local
npx supabase db diff -f add_new_feature
# Review, test with db reset, then commit
```

See [Schema Migrations](schema-migrations.md) for the full workflow.

---

<div align="center">

[⬆ Back to Development Guide](README.md) | [⬆ Back to Documentation Hub](../README.md)

</div>
