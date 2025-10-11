# Deprecated User Management Scripts

These scripts were used during migration and development but are now deprecated in favor of `manage_users.py`.

## Archived Scripts

### Migration Scripts (One-time use, completed)
- `fix_user_login.py` - Fixed user login during email→username migration
- `fix_user_profile.py` - Fixed profile access issues during migration
- `migrate_user_to_username.py` - Migrated users from email to username auth

### Redundant Scripts (Replaced by manage_users.py)
- `list_auth_users.py` - Use: `manage_users.py list`
- `reset_user_password.py` - Use: `manage_users.py password`
- `make_user_admin.py` - Use: `manage_users.py role --role admin`
- `check_user.py` - Use: `manage_users.py info`
- `check_users.py` - Use: `manage_users.py list`
- `create_test_user.py` - Use: `manage_users.py create`

## Current User Management

Use the comprehensive CLI tool:
```bash
uv run python manage_users.py --help
```

See `README_MANAGE_USERS.md` for complete documentation.

**Archived:** 2025-10-10
