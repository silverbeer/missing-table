# Test Users Seeding

## Overview

The Missing Table project uses three standard test users for development and testing. These users are automatically created/updated after database restores.

## Test Users

| Username | Password | Role | Purpose |
|----------|----------|------|---------|
| tom | testpass123 | admin | Full admin access for testing admin features |
| tom_ifa | testpass123 | team-manager | Team manager for IFA team |
| tom_ifa_fan | testpass123 | team-fan | Regular user/fan for IFA team |

**Note:** These users are stored in Supabase Authentication with internal email format (`username@missingtable.local`), but you login using just the username.

## Automatic Seeding

Test users are automatically seeded after running:
```bash
./scripts/db_tools.sh restore [file] [env]
```

The restore operation will:
1. Restore database tables from backup
2. Automatically call `./scripts/seed_test_users.sh`
3. Create/update the 3 test users
4. Assign team associations (if IFA team exists)

## Manual Seeding

You can also manually seed test users anytime:

```bash
# Local environment (default)
./scripts/seed_test_users.sh

# Specific environment
./scripts/seed_test_users.sh local
./scripts/seed_test_users.sh dev
./scripts/seed_test_users.sh prod
```

## User Management

For more advanced user management:

```bash
cd backend

# List all users
APP_ENV=local uv run python manage_users.py list

# Get user details
APP_ENV=local uv run python manage_users.py info --user tom

# Change role
APP_ENV=local uv run python manage_users.py role --user tom --role admin

# Assign team
APP_ENV=local uv run python manage_users.py team --user tom_ifa --team-id 1

# List teams
APP_ENV=local uv run python manage_users.py teams
```

## Notes

- **Password**: All test users use the same password (`testpass123`) for simplicity
- **Team Assignment**: If no IFA team is found during seeding, users are created without team assignments
- **Supabase Auth**: Users must sign in at least once before team assignments work (Supabase Auth requirement)
- **Environment-Specific**: Users are environment-specific (local, dev, prod have separate user databases)

## Security

⚠️ **Important**: These are **TEST USERS ONLY**. They should:
- Never be used in production
- Have simple, known passwords for development ease
- Be recreated regularly during development

## Troubleshooting

### Users created but not assigned to teams
If team assignments fail, users exist in Supabase Auth but aren't in `user_profiles` yet. Solution:
1. Sign in to the app with the user
2. Re-run the seed script: `./scripts/seed_test_users.sh`

### Team not found
If the seed script can't find an IFA team:
1. Check teams exist: `APP_ENV=local uv run python backend/manage_users.py teams`
2. Verify database restore completed successfully
3. Manually assign teams after checking team IDs

### Password doesn't work
If login fails:
1. Verify environment matches (local vs dev vs prod)
2. Check Supabase Studio for auth.users entries
3. Reset password: `APP_ENV=local uv run python backend/manage_users.py password --user tom@example.com`

## See Also

- [User Management Guide](./02-development/user-management.md)
- [Database Tools](./02-development/database-management.md)
- [Authentication Architecture](./03-architecture/authentication.md)
