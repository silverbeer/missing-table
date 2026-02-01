# Environment Management

> **Audience**: Developers
> **Prerequisites**: Basic understanding of development environments
> **Environments**: Local, Prod (Cloud)

Managing environments for development and production.

---

## Overview

The Missing Table application supports two environments:

1. **Local** - Local Supabase for offline development
2. **Prod** - Production Supabase (use with caution)

---

## Environment Switching

### Quick Commands

```bash
# Switch environments
./switch-env.sh local    # Local Supabase (default)
./switch-env.sh prod     # Cloud production

# Check current environment
./switch-env.sh status

# Show help
./switch-env.sh help
```

---

## Local Environment (Default)

### Characteristics

- **Offline capable** - Works without internet
- **Fast** - No network latency
- **Safe** - Isolated from cloud data
- **Best for**: E2E testing, offline development

### Configuration Files

```
backend/.env.local
frontend/.env.local
```

### Setup

```bash
# 1. Switch to local environment
./switch-env.sh local

# 2. Start local Supabase
supabase start

# 3. Restore data
./scripts/db_tools.sh restore

# 4. Start development
./missing-table.sh dev
```

### Local Environment Variables

**Backend** (`.env.local`):
```bash
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<from supabase status>
SUPABASE_SERVICE_KEY=<from supabase status>
SUPABASE_JWT_SECRET=<from supabase status>
```

**Frontend** (`.env.local`):
```bash
VUE_APP_API_URL=http://localhost:8000
VUE_APP_SUPABASE_URL=http://127.0.0.1:54321
VUE_APP_SUPABASE_ANON_KEY=<from supabase status>
```

---

## Production Environment

### Characteristics

- **Live data** - Real users, real consequences
- **Use with caution** - Always test locally first
- **Best for**: Production deployments only

### Configuration Files

```
backend/.env.prod
frontend/.env.prod
```

### Production Environment Variables

**Backend** (`.env.prod`):
```bash
SUPABASE_URL=https://prod-project.supabase.co
SUPABASE_ANON_KEY=<production key>
SUPABASE_SERVICE_KEY=<production key>
SUPABASE_JWT_SECRET=<production key>
ENVIRONMENT=production
```

---

## Environment-Aware Database Operations

All database operations support environment specification:

### Backup Operations

```bash
./scripts/db_tools.sh backup         # Current environment
./scripts/db_tools.sh backup local   # Local environment
```

### Restore Operations

```bash
./scripts/db_tools.sh restore                    # Latest backup to current env
./scripts/db_tools.sh restore backup_file.json  # Specific backup to current env
```

### Reset Operations (Local Only)

```bash
./scripts/db_tools.sh reset local    # Reset local database
```

---

## Development Workflows

### Testing Workflow

**Local testing (isolated)**:
```bash
./switch-env.sh local
supabase start
./scripts/db_tools.sh restore
./missing-table.sh start
```

---

## Secret Management

### Never Commit Environment Files!

All `.env`, `.env.local`, and `.env.prod` files are gitignored.

### Example Files

We provide `.example` files that can be copied:

```bash
# Backend
cp backend/.env.example backend/.env.local
# Edit backend/.env.local with your values

# Frontend
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local with your values
```

### Getting Supabase Keys

**Local**:
```bash
supabase status
# Copy the values shown
```

**Cloud**:
1. Go to Supabase Dashboard
2. Select your project
3. Go to Settings > API
4. Copy the keys

---

## Best Practices

### Do's

- Use **local** for daily development
- Test locally before deploying to **prod**
- Backup before switching environments
- Keep environment files private

### Don'ts

- Don't commit `.env` files
- Don't use prod for testing
- Don't share your API keys
- Don't hardcode environment values

---

## Troubleshooting

### Environment Not Switching

```bash
# Verify current environment
./switch-env.sh status

# Check environment files exist
ls -la backend/.env*
ls -la frontend/.env*

# Recreate from examples
cp backend/.env.example backend/.env.local
```

### Database Connection Errors

```bash
# For local: Restart Supabase
supabase stop
supabase start

# For cloud: Check credentials
cat backend/.env.prod
# Verify SUPABASE_URL and keys
```

### Data Missing After Switch

```bash
# Restore appropriate backup
./scripts/db_tools.sh restore  # Latest for current env
```

---

## Related Documentation

- **[Daily Workflow](daily-workflow.md)** - Common commands
- **[Database Operations](database-operations.md)** - Backup/restore
- **[Deployment](../05-deployment/)** - Production deployment
- **[Security](../06-security/)** - Secret management

---

<div align="center">

[⬆ Back to Development Guide](README.md) | [⬆ Back to Documentation Hub](../README.md)

</div>
