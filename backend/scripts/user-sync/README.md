# User Synchronization Between Environments

This directory contains utilities to keep auth users synchronized between dev and production environments, ensuring test users can use the same credentials in both environments.

## Problem

Test users need to access both dev and production environments without maintaining separate credentials for each environment.

## Solution

Use the `sync_users.py` script to synchronize users from one environment to another.

## Quick Start

### Sync Dev Users to Production

```bash
# Dry run first (see what would happen)
cd backend
APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod --dry-run

# Actually sync with custom password
APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod --password "TestPass123!"
```

### Sync Production Users to Dev

```bash
# Sync prod → dev
cd backend
APP_ENV=prod uv run python scripts/user-sync/sync_users.py --to dev --password "TestPass123!"
```

## How It Works

1. **Fetches users** from source environment using Supabase Admin API
2. **Compares** with target environment users (matches by email)
3. **Creates missing users** in target environment with specified password
4. **Preserves user metadata** (display_name, roles, etc.)

## Password Strategy

The script supports several password strategies:

### Option 1: Specify password via flag (Recommended)
```bash
APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod --password "TestPass123!"
```

### Option 2: Set environment variable
```bash
export SYNC_DEFAULT_PASSWORD="TestPass123!"
APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod
```

### Option 3: Use default (not recommended)
If no password is specified, uses default: `ChangeMe123!`

**After sync, users should:**
1. Log in with the sync password
2. Change their password immediately
3. OR request a password reset via the app

## Important Notes

### Password Limitations

⚠️ **Supabase does not allow exporting hashed passwords via API**

This means:
- Passwords cannot be copied from source to target
- New users are created with a known/temporary password
- Users must change password or reset it after first sync

### User Metadata Preserved

✅ The following user data **is** preserved:
- Email address
- Display name
- User metadata (roles, team associations, etc.)
- Email confirmation status

❌ The following **cannot** be preserved:
- Password (users get new password)
- Last sign-in date
- Session tokens

## Common Workflows

### New Test User Flow

1. **Create user in dev environment**
   ```bash
   # User signs up in dev via app
   # Email: alice@example.com
   ```

2. **Sync to production**
   ```bash
   cd backend
   APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod --password "Test2025!"
   ```

3. **User can now log in to both environments**
   - Dev: alice@example.com / (original password)
   - Prod: alice@example.com / Test2025!

4. **User changes prod password via app**

### Onboarding Multiple Test Users

```bash
# 1. Create all test users in dev environment (via app signup)

# 2. Sync all users to prod at once
cd backend
APP_ENV=dev uv run python scripts/user-sync/sync_users.py --to prod --password "Welcome2025!"

# 3. Send welcome email with:
#    - Dev URL: https://dev.missingtable.com
#    - Prod URL: https://missingtable.com
#    - Credentials: <email> / Welcome2025!
#    - Instructions to change password
```

## Backup Users

To backup current users (for reference or rollback):

```bash
cd backend
APP_ENV=dev uv run python scripts/user-sync/backup_auth_users.py
# Creates: auth_users_dev_YYYYMMDD_HHMMSS.json

APP_ENV=prod uv run python scripts/user-sync/backup_auth_users.py
# Creates: auth_users_prod_YYYYMMDD_HHMMSS.json
```

Backups are automatically gitignored and stored in `backend/` temporarily. Move to `backups/user-migrations/` for safekeeping.

## Security Considerations

1. **Never commit user backups to git** - They contain emails and UUIDs (gitignored)
2. **Use strong sync passwords** - At least 12 characters with mixed case, numbers, symbols
3. **Rotate sync passwords** - Don't reuse the same password for multiple syncs
4. **Limit who can run sync** - Only trusted team members should have access to both env files
5. **Monitor user creation** - Check Supabase Dashboard after sync to verify

## Troubleshooting

### "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY"

Make sure you have both `.env.dev` and `.env.prod` files with Supabase credentials:

```bash
# backend/.env.dev
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=xxx

# backend/.env.prod
SUPABASE_URL=https://yyy.supabase.co
SUPABASE_SERVICE_KEY=yyy
```

### "Failed to create user: 422"

This usually means:
- Password doesn't meet Supabase requirements (min 6 characters)
- Email is invalid
- User already exists but wasn't detected

### Users created but can't log in

1. Check password meets requirements
2. Verify email is confirmed (should be auto-confirmed)
3. Check Supabase Dashboard → Authentication → Users
4. Try password reset via app

## Files

- `sync_users.py` - Main sync script
- `backup_auth_users.py` - Backup users to JSON
- `README.md` - This file

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Main project documentation
- [Database Tools](../../../scripts/db_tools.sh) - Database backup/restore
- [User Administration](../../make_user_admin.py) - Grant admin roles
