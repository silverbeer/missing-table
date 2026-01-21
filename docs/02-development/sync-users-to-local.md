# Syncing Users to Local Supabase

This guide explains how to use the `sync_users_to_local.py` CLI tool to copy users from cloud Supabase (production) to your local Supabase instance for development and testing.

## Overview

When developing locally, you often need real user data to test features. This tool:
- Copies users from cloud to local Supabase
- Assigns known passwords based on user roles (for easy testing)
- Syncs `user_profiles`, `team_manager_assignments`, and `player_team_history`
- Excludes test users by default

## Password Mapping

Users are assigned passwords based on their role:

| Role | Password |
|------|----------|
| admin | admin123 |
| team-manager / team_manager | team123 |
| club_manager / club-manager | club123 |
| team-player / team_player | play123 |
| team-fan / team_fan | fan123 |
| club-fan / club_fan | fan123 |
| user (default) | fan123 |

## Prerequisites

1. **Local Supabase running**: `cd supabase-local && npx supabase start`
2. **Environment files configured**:
   - `backend/.env.local` - Local Supabase credentials
   - `backend/.env.prod` - Production Supabase credentials

## Usage

### Basic Sync

Sync all real users from production to local (excludes test users):

```bash
cd backend && uv run python scripts/sync_users_to_local.py --from prod
```

### Filter by Username

Sync specific users:

```bash
cd backend && uv run python scripts/sync_users_to_local.py --from prod --users tom,tom_ifa,eric_ifa
```

Use SQL LIKE pattern matching:

```bash
# All users starting with "tom"
cd backend && uv run python scripts/sync_users_to_local.py --from prod --filter "tom%"
```

### Filter by Role

Sync users with specific roles:

```bash
# Single role
cd backend && uv run python scripts/sync_users_to_local.py --from prod --role admin

# Multiple roles
cd backend && uv run python scripts/sync_users_to_local.py --from prod --role team-manager,club_manager
```

### Include Test Users

By default, these username patterns are excluded:
- `contract_test_%`
- `test_login_%`
- `duplicate_%`

To include all users:

```bash
cd backend && uv run python scripts/sync_users_to_local.py --from prod --include-all
```

### Dry Run

Preview changes without making them:

```bash
cd backend && uv run python scripts/sync_users_to_local.py --from prod --dry-run
```

### Force Overwrite

By default, existing users are skipped. To overwrite (delete and recreate):

```bash
cd backend && uv run python scripts/sync_users_to_local.py --from prod --force
```

## Helper Commands

### List Cloud Users

Preview users in cloud without syncing:

```bash
cd backend && uv run python scripts/sync_users_to_local.py list-cloud --from prod
```

### Show Password Mapping

Display the role-to-password mapping:

```bash
cd backend && uv run python scripts/sync_users_to_local.py passwords
```

## Data Synced

For each user, the tool syncs:

1. **auth.users**
   - User ID (preserved from source)
   - Email (converted to `{username}@missingtable.local`)
   - Password (based on role)
   - User metadata

2. **user_profiles**
   - id, username, role, display_name
   - email, phone_number
   - team_id, club_id
   - player_number, positions
   - assigned_age_group_id, invited_via_code

3. **team_manager_assignments**
   - user_id, team_id (for multi-team managers)

4. **player_team_history**
   - player_id, team_id, season_id
   - age_group_id, league_id, division_id
   - jersey_number, positions
   - is_current, notes (for player roster tracking)

## Example Workflow

1. **Preview users to sync**:
   ```bash
   cd backend && uv run python scripts/sync_users_to_local.py --from prod --dry-run
   ```

2. **Sync specific user**:
   ```bash
   cd backend && uv run python scripts/sync_users_to_local.py --from prod --users tom
   ```

3. **Login to local**:
   - Open http://localhost:8080
   - Login with: `tom` / `admin123`

4. **Verify in Supabase Studio**:
   - Open http://127.0.0.1:54333/project/default
   - Check `user_profiles` table

## Troubleshooting

### "Environment file not found"

Ensure you have the correct `.env.{env}` files in the `backend/` directory.

### "User already exists"

Use `--force` to overwrite existing users, or manually delete them first.

### Team/Club references fail

The tool only syncs user data. Ensure your local database has the required teams/clubs from production (or use `--force` which ignores FK constraints during user creation).

## Related Tools

- `manage_users.py` - Create/edit users directly in any environment
- `switch-env.sh` - Switch between local and prod environments
- `db_tools.sh restore` - Restore database from backup
