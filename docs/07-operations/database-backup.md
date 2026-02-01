# Database Backup & Restore Guide

This guide covers the backup and restore system for the MLS Next application development database.

## Quick Start

Use the convenient shell script for common operations:

```bash
# Create a backup
./scripts/db_tools.sh backup

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

## Backup System

### What Gets Backed Up

The backup system creates JSON exports of all important tables:

- **Reference Data**: Age groups, divisions, match types, seasons
- **Teams & Mappings**: Teams, team mappings, team-match type associations
- **Matches**: All match records
- **User Profiles**: User profile data (without sensitive auth info)

### Backup Files

- Location: `backups/` directory
- Format: `database_backup_YYYYMMDD_HHMMSS.json`
- Contains metadata about when backup was created
- Structured JSON with tables and data

### Creating Backups

**Option 1: Using the convenience script**
```bash
./scripts/db_tools.sh backup
```

**Option 2: Direct Python script**
```bash
cd backend
uv run python ../scripts/backup_database.py
```

**Option 3: Programmatic backup with options**
```bash
cd backend
uv run python ../scripts/backup_database.py --list        # List existing backups
uv run python ../scripts/backup_database.py --cleanup 10  # Keep only 10 backups
```

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

## File Structure

```
project/
├── scripts/
│   ├── db_tools.sh              # Main utility script
│   ├── backup_database.py       # Backup script
│   └── restore_database.py      # Restore script
├── backend/
│   └── [DEPRECATED] populate_teams_supabase.py  # Use db_tools.sh instead
└── backups/
    ├── database_backup_20231220_143022.json
    ├── database_backup_20231220_151505.json
    └── ...
```

## Backup File Format

```json
{
  "backup_info": {
    "timestamp": "20231220_143022",
    "created_at": "2023-12-20T14:30:22.123456",
    "version": "1.0",
    "supabase_url": "http://127.0.0.1:54321"
  },
  "tables": {
    "teams": [
      {"id": 1, "name": "IFA", "city": "New York", ...},
      ...
    ],
    "matches": [...],
    ...
  }
}
```

## Troubleshooting

### Common Issues

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