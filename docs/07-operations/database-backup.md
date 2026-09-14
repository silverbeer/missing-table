# Database Backup & Restore Guide

This guide covers the backup and restore system for the MLS Next application development database.

## Quick Start

Use the convenient shell script for common operations:

```bash
# Create a backup from production (the default)
./scripts/db_tools.sh backup

# Create a backup of local Supabase
./scripts/db_tools.sh backup local

# List available backups
./scripts/db_tools.sh list

# Restore from latest backup
./scripts/db_tools.sh restore

# Restore from specific backup
./scripts/db_tools.sh restore database_backup_20231220_143022.json

# Reset database and restore from latest backup (PREFERRED)
# NOTE: Requires a backup less than 4 hours old (safety guard)
./scripts/db_tools.sh reset

# Clean up old backups (keep only 5 most recent)
./scripts/db_tools.sh cleanup 5
```

### Refresh Local from Production (Recommended)

The easiest way to sync your local database with production:

```bash
./scripts/setup-local-db.sh --from-prod
```

This single command:
1. Creates a fresh backup from prod
2. Resets local database (applies schema + seed)
3. Restores match/team data from the fresh backup
4. Flushes Redis cache
5. Seeds test users (tom, tom_ifa, etc.)

## Backup System

### What Gets Backed Up

The backup system creates JSON exports of all important tables:

- **Reference Data**: Age groups, divisions, match types, seasons
- **Teams & Mappings**: Teams, team mappings, team-match type associations
- **Matches**: All match records
- **User Profiles**: User profile data (without sensitive auth info)

### Backup Files

- Location: `~/backups/missing-table/` (override with `--backup-dir`)
- Format: `database_backup_YYYYMMDD_HHMMSS.json.gz`
- `backup_info` records when, from which environment (`app_env`, `supabase_url`), and rows per table
- Structured JSON with tables and data

### Which environment gets backed up

Backups default to **production** (SB-1069). `APP_ENV` is ignored on purpose: shells here export
`APP_ENV=local`, and reading it is how a bare `backup` twice backed up a stopped local database instead
of production. Local is backed up only when you ask for it:

```bash
./scripts/db_tools.sh backup         # production
./scripts/db_tools.sh backup local   # local Supabase (must be running)
```

`./scripts/db_tools.sh migrate prod` takes its own production backup; you do not need one first.

### Creating Backups

**Option 1: Using the convenience script**
```bash
./scripts/db_tools.sh backup
```

**Option 2: Direct Python script**
```bash
cd backend
uv run python ../scripts/backup_database.py              # production
uv run python ../scripts/backup_database.py --env local  # local Supabase
```

**Option 3: Programmatic backup with options**
```bash
cd backend
uv run python ../scripts/backup_database.py --list                 # List backups, flagging incomplete ones
uv run python ../scripts/backup_database.py --cleanup --keep-days 30  # Apply the retention policy
```

### A backup is complete or it is not written

A failed backup used to write a file anyway and exit 0 — with the database down it wrote a zero-table
backup that `restore --latest` would then have picked, and restore clears every table before loading
(SB-1068). The script now:

| Situation | What happens |
|-----------|--------------|
| Database unreachable | Fails at a connection check naming the environment and the URL; for local, suggests `npx supabase start` |
| Network error, timeout, 5xx (incl. Supabase's gateway 504) | Retried after 1s, 2s, 4s; then the table fails |
| Permanent error (missing table, permission denied) | Not retried; the table fails |
| A table fails | The run carries on so the report names every failed table — unless the database stopped responding, then it stops |
| Fewer rows read than PostgREST counted | The table fails rather than being saved short |
| `auth.users` cannot be read | The backup fails |
| A seeded reference table (`age_groups`, `leagues`, `divisions`, `match_types`, `seasons`) is empty | The backup fails — that is not a real database |
| Disk full, crash or Ctrl-C while writing | Written to a hidden `.partial` file, read back, then renamed; a failed write leaves nothing |

Exit codes: **0** complete backup written, **1** failed (nothing written), **130** cancelled.
`db_tools.sh` and `run_backup.sh` both act on that code. User-generated tables (players, lineups, match
events) being empty is normal and is not a failure.

## Backup Freshness Guard

The `db_tools.sh reset` command includes a **4-hour safety guard**. Before resetting the database, it checks that a backup exists that was created less than 4 hours ago. If the latest backup is older, the reset is aborted to prevent data loss from a stale backup.

```bash
# If reset fails due to stale backup:
./scripts/db_tools.sh backup    # Create a fresh backup first
./scripts/db_tools.sh reset     # Now reset will succeed
```

This ensures you always have a recent restore point before a destructive reset operation.

## Restore System

### What Gets Restored

The restore system can:
- Clear existing data (default) or append to existing data
- Restore tables in dependency order (respects foreign keys)
- Handle missing tables gracefully
- Provide detailed progress feedback

### Restoring Data

**Option 1: Restore latest backup**
```bash
./scripts/db_tools.sh restore
```

**Option 2: Restore specific backup**
```bash
./scripts/db_tools.sh restore database_backup_20231220_143022.json
```

**Option 3: Direct Python script**
```bash
cd backend
uv run python ../scripts/restore_database.py --latest
uv run python ../scripts/restore_database.py backup_file.json
uv run python ../scripts/restore_database.py --list  # List available backups
```

**Option 4: Restore without clearing existing data**
```bash
cd backend
uv run python ../scripts/restore_database.py backup_file.json --no-clear
```

## Development Workflow

### Recommended Workflow

1. **Before Major Changes**: Always create a backup
   ```bash
   ./scripts/db_tools.sh backup
   ```

2. **After Database Schema Changes**: Reset and repopulate
   ```bash
   ./scripts/db_tools.sh reset
   ```

3. **When Things Go Wrong**: Restore from backup
   ```bash
   ./scripts/db_tools.sh restore
   ```

4. **Weekly Cleanup**: Keep backups manageable
   ```bash
   ./scripts/db_tools.sh cleanup 10
   ```

### Common Scenarios

**Scenario 1: Testing New Features**
```bash
# 1. Create backup before testing
./scripts/db_tools.sh backup

# 2. Test your feature...

# 3. If something breaks, restore
./scripts/db_tools.sh restore
```

**Scenario 2: Database Schema Migration**
```bash
# 1. Backup current state
./scripts/db_tools.sh backup

# 2. Apply migrations (use db reset only for schema changes)
npx supabase db reset

# 3. Restore real data from backup (PREFERRED - maintains real data)
./scripts/db_tools.sh restore
```

**Scenario 3: Switching Branches**
```bash
# 1. Backup current branch state
./scripts/db_tools.sh backup

# 2. Switch branches
git checkout feature-branch

# 3. Reset database and restore real data for new branch
./scripts/db_tools.sh reset
```

**Scenario 4: Sync Local with Production Data**
```bash
# Single command to refresh local from prod
./scripts/setup-local-db.sh --from-prod

# This backs up from prod, resets local, restores data, and seeds test users
```

## File Structure

```
project/
├── scripts/
│   ├── db_tools.sh              # Main utility script
│   ├── backup_database.py       # Backup script
│   └── restore_database.py      # Restore script
├── backend/
│   └── [DEPRECATED] populate_teams_supabase.py  # Use db_tools.sh instead
└── backend/tests/unit/test_backup_database.py   # Failure-path tests (SB-1068)

~/backups/missing-table/
├── database_backup_20260914_073207.json.gz
├── database_backup_20260907_135105.json.gz
└── ...
```

## Backup File Format

```json
{
  "backup_info": {
    "timestamp": "20260914_073207",
    "created_at": "2026-09-14T07:32:13.117869",
    "version": "1.1",
    "app_env": "prod",
    "supabase_url": "https://<project>.supabase.co",
    "row_counts": {"teams": 1234, "matches": 7286, "players": 0, "...": 0}
  },
  "tables": {
    "teams": [
      {"id": 1, "name": "IFA", "city": "New York", ...},
      ...
    ],
    "matches": [...],
    "auth_users": [...],
    ...
  }
}
```

`app_env` and `row_counts` were added in version 1.1; older backups lack them and `--list` shows their
environment as `unknown`. `--list` marks any backup missing a table, or with an empty seeded table, as
`⚠ INCOMPLETE` — do not restore from one.

## Troubleshooting

### Common Issues

**0. "❌ Backup failed … No backup was written"**
- The lines under it name every table that failed and why
- `Cannot read from Supabase … (local)` — local Supabase is stopped. Run `npx supabase start`, or you
  meant production, which is the default: `./scripts/db_tools.sh backup`
- `--env prod, but SUPABASE_URL is … a local address` (or the reverse) — `backend/.env.<env>` points at
  the wrong database; fix the file rather than the flag
- `not attempted — the database stopped responding` — the connection dropped mid-backup; rerun it
- `read N of M rows` — PostgREST returned fewer rows than it counted; rerun, and if it repeats check the
  project's max-rows setting

**1. "supabase_key is required" Error**
- Ensure Supabase is running: `npx supabase start`
- Check `.env.local` file exists in backend directory

**2. "Permission denied" on restore**
- Make sure you're using the service key, not anon key
- Check environment variables are loaded correctly

**3. Backup files getting too large**
- Run cleanup to remove old backups: `./scripts/db_tools.sh cleanup 5`
- Consider archiving important backups elsewhere

**4. Restore fails with foreign key errors**
- The script handles dependency order automatically
- If issues persist, try `./scripts/db_tools.sh reset` instead

### Environment Requirements

- Python 3.13+ with uv package manager
- Supabase CLI installed and configured
- Local Supabase instance running
- Proper environment variables in `backend/.env.local`

### Recovery from Total Loss

If you lose all data and backups:

1. Reset database schema: `npx supabase db reset`
2. Repopulate basic data: `./scripts/db_tools.sh reset`
3. Manually recreate user accounts through the UI
4. Re-enter any custom match/team data

## Best Practices

1. **Backup Before Major Changes**: Always create a backup before:
   - Database schema changes
   - Major feature development
   - Data migration scripts
   - Switching git branches with DB changes

2. **Regular Cleanup**: Keep only recent backups to save disk space
   ```bash
   ./scripts/db_tools.sh cleanup 10  # Keep 10 most recent
   ```

3. **Meaningful Backup Names**: The automated timestamps are good, but consider manual copies for important milestones

4. **Test Restores**: Periodically test that your backups can be restored successfully

5. **Document Data Changes**: Keep notes about what data was in each backup for easier recovery

## Security Notes

- Backup files contain all non-sensitive database data
- Auth passwords and sensitive tokens are NOT included
- User email addresses are included in auth metadata
- Store backup files securely if they contain production data
- Never commit backup files to git (they're in .gitignore)

## Integration with Development

The backup system integrates well with:
- **Git workflow**: Create backups when switching branches
- **Testing**: Backup before tests, restore after
- **Feature development**: Isolate data changes per feature
- **Team collaboration**: Share known-good database states

---

*For questions or issues with the backup system, check the script help:*
```bash
./scripts/db_tools.sh help
```
