# MCP (Model Context Protocol) Setup

This project uses MCP to provide Claude Code with direct access to the Supabase database for queries.

## Setup Instructions

### 1. Install Supabase MCP Server

```bash
npm install -g supabase-mcp
```

### 2. Configure Environment Variable

The `.mcp.json` file references the `SUPABASE_PG_URL` environment variable for security.

Add this to your shell profile (`~/.zshrc` for zsh or `~/.bashrc` for bash):

```bash
# pragma: allowlist secret
export SUPABASE_PG_URL="postgresql://postgres.PROJECT_ID:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
```

**Replace `PROJECT_ID` and `YOUR_PASSWORD` with your actual Supabase project ID and database password.**

To get your Supabase PostgreSQL connection string:
1. Go to your Supabase project dashboard
2. Navigate to **Project Settings** → **Database**
3. Under **Connection String**, select **Connection pooling** (recommended)
4. Copy the URI and replace the password placeholder

### 3. Reload Your Shell

After adding the environment variable:

```bash
source ~/.zshrc  # or source ~/.bashrc
```

### 4. Verify MCP Configuration

The `.mcp.json` file should look like this:

```json
{
  "mcpServers": {
    "supabase-sql": {
      "command": "supabase-mcp",
      "env": {
        "SUPABASE_PG_URL": "${SUPABASE_PG_URL}",
        "NODE_TLS_REJECT_UNAUTHORIZED": "0"
      }
    }
  }
}
```

### 5. Restart Claude Code

For the changes to take effect, restart Claude Code or your editor.

## Usage

Once configured, Claude Code can query the database directly:

```javascript
// Example: Claude can run SQL queries like this
SELECT id, username, role, team_id FROM user_profiles WHERE role = 'team-manager';
```

## Security Notes

- ✅ **DO** keep `.mcp.json` in git (it only references environment variables)
- ✅ **DO** add database credentials to your shell profile (gitignored by default)
- ❌ **DON'T** commit actual passwords or connection strings to git
- ❌ **DON'T** share your `SUPABASE_PG_URL` value publicly

## Troubleshooting

### MCP server not connecting

1. Verify the environment variable is set:
   ```bash
   echo $SUPABASE_PG_URL
   ```

2. Check that `supabase-mcp` is installed:
   ```bash
   which supabase-mcp
   ```

3. Restart Claude Code completely

### Connection timeout

- Check your Supabase project is running
- Verify the connection string is correct
- Ensure your IP is allowed in Supabase firewall rules

## Related Documentation

- [MCP Documentation](https://github.com/anthropics/model-context-protocol)
- [Supabase MCP Server](https://github.com/supabase/mcp-server-supabase)
- [Project Secret Management](./docs/SECRET_MANAGEMENT.md)
