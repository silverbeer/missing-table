# 💻 Daily Development Workflow

> **Audience**: Developers
> **Time**: Reference guide
> **Source**: Extracted from CLAUDE.md

Common commands and patterns for daily development on the Missing Table project.

---

## 🚀 Quick Reference

### Service Management

```bash
# Primary service management script
./missing-table.sh dev      # Start with auto-reload (RECOMMENDED)
./missing-table.sh start    # Start both backend and frontend
./missing-table.sh stop     # Stop all running services
./missing-table.sh restart  # Restart all services
./missing-table.sh status   # Show service status and PIDs
./missing-table.sh logs     # View recent service logs (static)
./missing-table.sh tail     # Follow logs in real-time (Ctrl+C to stop)
```

**Development mode features**:
- Backend: Auto-reload on Python file changes (uvicorn --reload)
- Frontend: Hot module replacement on Vue file changes (built-in)
- No need to restart after code changes!

### Alternative Start Methods

```bash
# Frontend only (http://localhost:8081)
cd frontend && npm run serve

# Backend only (http://localhost:8000)
cd backend && uv run python app.py

# Run backend tests
cd backend && uv run pytest

# Lint frontend
cd frontend && npm run lint
```

---

## 🗄️ Database Operations

### Database Backup & Restore

```bash
# Refresh local database from production (RECOMMENDED)
./scripts/setup-local-db.sh --from-prod

# Database backup and restore utility
./scripts/db_tools.sh restore        # Restore from latest backup
./scripts/db_tools.sh restore backup_file.json  # Restore from specific backup
./scripts/db_tools.sh backup         # Create new backup
APP_ENV=prod ./scripts/db_tools.sh backup  # Create backup from prod
./scripts/db_tools.sh list           # List available backups
./scripts/db_tools.sh cleanup 5      # Keep only 5 most recent backups
```

**Recommended workflow**: Use `./scripts/setup-local-db.sh --from-prod` to get a complete refresh from production data.

### Supabase Commands

```bash
# Supabase CLI (installed via Homebrew)
supabase start    # Start local Supabase
supabase stop     # Stop local Supabase
supabase status   # Check status and get URLs
```

---

## 🌍 Environment Management

The application supports two environments: **local** and **prod** (cloud).

### Environment Switching

```bash
# Switch environments
./switch-env.sh local    # Local Supabase (default)
./switch-env.sh prod     # Cloud production

# Check current environment
./switch-env.sh status

# Show help
./switch-env.sh help
```

### Environment Configurations

**1. Local Environment (Default)**:
- Uses local Supabase instance
- Requires `supabase start`
- Best for e2e testing and offline development
- Configuration: `backend/.env.local`, `frontend/.env.local`

**2. Production Environment**:
- Uses production Supabase project
- Configuration: `backend/.env.prod`, `frontend/.env.prod`
- Use with caution - production data

---

## 🐳 Docker Image Building

**CRITICAL**: Always use the `build-and-push.sh` script to build Docker images.

This script handles platform-specific builds correctly (ARM64 for Mac, AMD64 for GKE).

```bash
# Build for cloud deployment (AMD64, push to registry)
./build-and-push.sh backend dev      # Dev environment
./build-and-push.sh frontend prod    # Production environment
./build-and-push.sh all dev          # Build all services for dev

# Build for local development (current platform, no push)
./build-and-push.sh backend local
./build-and-push.sh frontend local

# After building for cloud, deploy to Kubernetes:
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
```

**Why this script is required**:
- GKE clusters run on AMD64 architecture
- Mac computers use ARM64 architecture
- Docker images must match the deployment platform
- Manual docker build commands often fail with "no match for platform" errors

---

## 👥 User Administration

### Make User Admin (after users sign up)

```bash
cd backend && uv run python make_user_admin.py --list              # List all users
cd backend && uv run python make_user_admin.py --user-id USER_ID   # Make specific user admin
cd backend && uv run python make_user_admin.py --interactive       # Interactive mode
```

### Available Admin Scripts

- `make_user_admin.py`: Comprehensive user role management (RECOMMENDED)
- `create_admin_invite.py`: Creates invitation codes for new admin users
- `reset_user_password.py`: Reset user passwords in cloud environment

### Password Reset (Cloud Environment)

```bash
cd backend && uv run python reset_user_password.py --email "user@example.com" --password "newpassword" --confirm
```

---

## 🧹 Duplicate Match Cleanup

Interactive tool to find and clean up duplicate matches:

```bash
# Scan for duplicates without making changes
cd backend && uv run python scripts/utilities/cleanup_duplicate_matches.py scan

# Show database statistics
cd backend && uv run python cleanup_duplicate_matches.py stats

# Preview what would be deleted (dry run)
cd backend && uv run python cleanup_duplicate_matches.py clean --dry-run

# Interactive mode - review and choose what to delete
cd backend && uv run python cleanup_duplicate_matches.py interactive

# Automatic cleanup (with backup)
cd backend && uv run python cleanup_duplicate_matches.py clean --no-dry-run

# Export duplicates to JSON for analysis
cd backend && uv run python scripts/utilities/cleanup_duplicate_matches.py scan --format json --save duplicates.json
```

---

## 🏥 System Health Monitoring

### Comprehensive Uptime Test

```bash
# Run comprehensive uptime test (requires backend dependencies)
cd backend && uv run python ../scripts/uptime_test.py

# This test verifies:
# - Local Supabase database connectivity
# - Backend API health and endpoints
# - Frontend accessibility
# - End-to-end data flow
# - Kubernetes deployment status
# - Authentication endpoints
# - Login functionality (with headless playwright)
```

### Health Check Endpoints

```bash
# Basic health check
curl http://localhost:8000/health

# Full health check with database status
curl http://localhost:8000/health/full
```

---

## 📊 Development Workflows

### Daily Development

**Local Development**:
```bash
# Start local development
./switch-env.sh local
cd supabase-local && npx supabase start && cd ..

# Option A: Restore from existing local backup
./scripts/db_tools.sh restore

# Option B: Refresh from production (gets latest data)
./scripts/setup-local-db.sh --from-prod

# Your development work...

# End of session
./missing-table.sh stop
```

### Testing New Features

```bash
# Before major changes (environment-aware)
./scripts/db_tools.sh backup     # Create safety backup for current environment

# After testing, if things go wrong
./scripts/db_tools.sh restore    # Restore to last known good state
```

### Database Schema Changes

```bash
# 1. Backup current data
./scripts/db_tools.sh backup

# 2. Apply schema migrations
supabase db reset            # ONLY for schema changes

# 3. Restore real data
./scripts/db_tools.sh restore    # Restore from backup (data survives schema changes)
```

---

## 🔧 Troubleshooting

### Service Won't Start

```bash
# Check if ports are in use
lsof -i :8000  # Backend
lsof -i :8081  # Frontend
lsof -i :54321 # Supabase

# Kill process if needed
kill -9 <PID>
```

### Database Issues

```bash
# Restart Supabase
supabase stop
supabase start

# Verify status
supabase status

# Check connection
./scripts/db_tools.sh list
```

### Build Errors

```bash
# Backend: Reinstall dependencies
cd backend
uv sync --reinstall

# Frontend: Clear cache
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 📖 Related Documentation

- **[Environment Management](environment-management.md)** - Detailed environment guide
- **[Database Operations](database-operations.md)** - Database management
- **[Docker Guide](docker-guide.md)** - Docker best practices
- **[Testing](../04-testing/)** - Testing strategy

---

<div align="center">

[⬆ Back to Development Guide](README.md) | [⬆ Back to Documentation Hub](../README.md)

</div>
