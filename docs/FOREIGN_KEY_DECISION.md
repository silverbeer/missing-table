# Foreign Key Constraints Decision

## Date: 2025-10-28

## Context

During the dev-to-production promotion, we removed three foreign key constraints from production:

```sql
ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS user_profiles_id_fkey;
ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_created_by_fkey;
ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_updated_by_fkey;
```

These constraints linked our tables to Supabase's `auth.users` table.

## Decision: Do NOT Add Constraints Back

**Reasoning:**

1. **Data Compatibility**: The dev data (now in prod) contains user_profiles with UUIDs that don't exist in auth.users
   - Creating auth.users for test data would require valid emails and authentication setup
   - Test data would pollute the auth system

2. **Application Independence**: The application currently works without these constraints
   - user_profiles are managed directly in our table
   - No dependency on Supabase Auth for basic functionality

3. **Flexibility**: Without FK constraints, we can:
   - Manage users independently of Supabase Auth
   - Use test data for development
   - Not worry about auth.users sync issues

## Future Considerations

If you want to re-enable Supabase Auth integration:

1. **Clean up user_profiles**: Ensure all user_profiles.id values exist in auth.users
2. **Create auth users**: Use Supabase Auth API to create users for any missing entries
3. **Add constraints back**:
   ```sql
   ALTER TABLE user_profiles
   ADD CONSTRAINT user_profiles_id_fkey
   FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

   ALTER TABLE matches
   ADD CONSTRAINT matches_created_by_fkey
   FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL;

   ALTER TABLE matches
   ADD CONSTRAINT matches_updated_by_fkey
   FOREIGN KEY (updated_by) REFERENCES auth.users(id) ON DELETE SET NULL;
   ```

## Current Status

✅ **Production is working correctly without these FK constraints**
✅ **All application functionality verified**
✅ **Decision: Leave constraints removed**

## Backup & Restore Strategy

**IMPORTANT**: Due to the UUID mismatch issue, we have implemented a separation between:
- **Match/Team Data**: Backed up and restored between environments
- **User Data**: Managed separately in each environment

### What Gets Backed Up

The backup/restore scripts (`scripts/backup_database.py` and `scripts/restore_database.py`) backup only:
- age_groups
- divisions
- match_types
- seasons
- teams
- team_mappings
- team_match_types
- matches

**user_profiles is EXCLUDED** from backups to prevent UUID mismatches.

### User Management Per Environment

Each environment (local, dev, prod) manages its own users:

```bash
# Create standard test users for an environment
./scripts/setup_environment_users.sh local
./scripts/setup_environment_users.sh dev
./scripts/setup_environment_users.sh prod

# Or manually manage users
cd backend
APP_ENV=prod uv run python manage_users.py create --email user@example.com --role admin
APP_ENV=prod uv run python manage_users.py list
APP_ENV=prod uv run python manage_users.py role --user user@example.com --role admin
```

### Why This Approach?

1. **UUID Integrity**: auth.users UUIDs are environment-specific and cannot be transferred
2. **Security**: Production users should be real accounts, not test data
3. **Flexibility**: Each environment can have different user sets
4. **Simplicity**: No complex user synchronization logic needed
