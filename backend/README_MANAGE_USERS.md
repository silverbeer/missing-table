# Missing Table User Management CLI

A comprehensive power tool for managing users in the Missing Table application.

## Features

- **List Users** - View all users with roles, teams, and details
- **Delete Users** - Remove users from auth and profiles
- **Change Passwords** - Reset passwords with secure generation
- **Create Users** - Add new users with roles
- **Update Roles** - Change user permissions
- **View Details** - Get comprehensive user information

## Commands

### List All Users
```bash
uv run python manage_users.py list
```

### Delete a User
```bash
# Interactive (prompts for confirmation)
uv run python manage_users.py delete --id <USER_ID>

# Skip confirmation
uv run python manage_users.py delete --id <USER_ID> --confirm
```

### Change Password
```bash
# Prompt for password
uv run python manage_users.py password --email <EMAIL>

# Provide password directly
uv run python manage_users.py password --email <EMAIL> --password <NEW_PASS>

# Generate secure password
uv run python manage_users.py password --email <EMAIL> --generate
```

### Create New User
```bash
# Interactive
uv run python manage_users.py create --email <EMAIL> --role <ROLE>

# With all options
uv run python manage_users.py create \
  --email user@example.com \
  --role team-fan \
  --display-name "John Doe" \
  --generate
```

### Update User Role
```bash
uv run python manage_users.py role --email <EMAIL> --role <NEW_ROLE>
```

Valid roles: `admin`, `team-manager`, `team-player`, `team-fan`

### View User Details
```bash
uv run python manage_users.py info --email <EMAIL>
```

## Environment Support

The tool automatically loads the correct environment based on `APP_ENV`:

```bash
# Default (dev)
uv run python manage_users.py list

# Explicit environment
APP_ENV=local uv run python manage_users.py list
APP_ENV=prod uv run python manage_users.py list
```

## Examples

### Common Operations

**List all team managers:**
```bash
uv run python manage_users.py list | grep "team-manager"
```

**Delete old/duplicate user:**
```bash
uv run python manage_users.py delete --id 8559d6a3-3298-47bc-a363-325795707fcc --confirm
```

**Reset password for user:**
```bash
uv run python manage_users.py password --email tom_ifa@missingtable.local --generate
```

**Create admin user:**
```bash
uv run python manage_users.py create \
  --email admin@missingtable.com \
  --role admin \
  --display-name "Admin User" \
  --generate \
  --confirm
```

## Security Notes

- **Passwords are hashed** - Cannot be retrieved, only reset
- **Confirmation required** - Use `--confirm` to skip prompts  
- **Environment-aware** - Always shows which environment you're working in
- **Audit trail** - All operations are logged

## Tips

- Use Tab completion: `uv run python manage_users.py --install-completion`
- Get help: `uv run python manage_users.py COMMAND --help`
- Skip confirmations in scripts: use `--confirm` or `-y` flag
- Generate secure passwords: use `--generate` or `-g` flag
