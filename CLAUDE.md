# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack web application for managing MLS Next sports league standings and game schedules. It uses FastAPI (Python 3.13+) for the backend and Vue 3 for the frontend, with Supabase as the primary database.

## Key Commands

### Development

#### Service Management
```bash
# Primary service management script
./missing-table.sh start    # Start both backend and frontend
./missing-table.sh stop     # Stop all running services
./missing-table.sh restart  # Restart all services
./missing-table.sh status   # Show service status and PIDs
./missing-table.sh logs     # View recent service logs (static)
./missing-table.sh tail     # Follow logs in real-time (Ctrl+C to stop)

# Handles processes started by Claude or manually
# Logs stored in ~/.missing-table/logs/
# Works with both local and dev environments
# tail command supports both multitail and standard tail -f
```

#### Alternative Start Methods
```bash
# Start with Supabase included
./start-with-supabase.sh

# Frontend only (http://localhost:8080)
cd frontend && npm run serve

# Backend only (http://localhost:8000)
cd backend && uv run python app.py

# Run backend tests
cd backend && uv run pytest

# Lint frontend
cd frontend && npm run lint
```

### Docker Compose (Local Development)
```bash
docker-compose up     # Start all services (uses external DB)
docker-compose down   # Stop all services
docker-compose build  # Rebuild images

# For completely self-contained setup with database:
docker-compose -f docker-compose.minimal.yml up
```

### Kubernetes with Helm (Rancher/Production)
```bash
cd helm && ./deploy-helm.sh    # Deploy to Rancher Kubernetes
helm upgrade missing-table ./missing-table --namespace missing-table
```

### When to use which:
- **Docker Compose**: Quick local development, testing single services, CI/CD
- **Helm/K8s**: Production deployment, scaling, team collaboration via Rancher

### HTTPS & Custom Domain (GKE)

The dev environment is deployed to GKE with HTTPS and custom domain:
- **Dev URL:** https://dev.missingtable.com
- **SSL:** Google-managed certificates (auto-renewing)
- **Load Balancer:** GCP Ingress (Application LB)

**Complete setup documentation:**
- [GKE HTTPS & Domain Setup Guide](./docs/GKE_HTTPS_DOMAIN_SETUP.md) - Full step-by-step guide
- [Quick Reference](./docs/HTTPS_QUICK_REFERENCE.md) - Common commands and troubleshooting

### Secret Management (GKE)

**SECURITY:** Secrets are managed using Kubernetes Secrets and are NEVER committed to git.

**Multi-layer protection:**
- 🔒 **Local pre-commit hook** (detect-secrets) - Blocks commits with secrets
- 🔒 **GitHub Actions CI/CD** (gitleaks + detect-secrets) - Scans every push/PR
- 🔒 **File system protection** (.gitignore) - Prevents staging secret files
- 🔒 **Scheduled scans** (Trivy) - Daily comprehensive security scans

**Documentation:**
- [Secret Management Guide](./docs/SECRET_MANAGEMENT.md) - Secret storage, detection, and prevention
- [Secret Runtime Loading](./docs/SECRET_RUNTIME_LOADING.md) - How secrets are loaded in local vs GKE

**Quick setup:**
```bash
# Copy example file and fill in real secrets
cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml
vim helm/missing-table/values-dev.yaml  # Add your secrets

# Deploy (creates Kubernetes Secret automatically)
helm upgrade missing-table ./missing-table -n missing-table-dev \
  --values ./missing-table/values-dev.yaml --wait
```

**Secret scanning tools:**
```bash
# Install detect-secrets
uv tool install detect-secrets

# Scan for secrets before commit
detect-secrets scan --baseline .secrets.baseline

# Pre-commit hook runs automatically
# Configured in: .husky/pre-commit
```

**Files:**
- `helm/missing-table/values-dev.yaml` - Real secrets (gitignored, local only)
- `helm/missing-table/values-dev.yaml.example` - Template (committed to git)
- `helm/missing-table/templates/secrets.yaml` - Kubernetes Secret template
- `.secrets.baseline` - detect-secrets baseline
- `.gitleaks.toml` - Gitleaks configuration

**Quick checks:**
```bash
# Check SSL certificate status
kubectl get managedcertificate -n missing-table-dev

# Check Ingress status
kubectl get ingress -n missing-table-dev

# Test HTTPS
curl -I https://dev.missingtable.com
```

### Database/Supabase
```bash
# Supabase CLI installed via Homebrew
supabase start    # Start local Supabase
supabase stop     # Stop local Supabase
supabase status   # Check status and get URLs

# IMPORTANT: Database Restoration
# NEVER use `npx supabase db reset` or seed sample data
# ALWAYS restore from the latest backup in the backups/ folder using db_tools.sh

# Database backup and restore utility
./scripts/db_tools.sh restore        # Restore from latest backup (PREFERRED)
./scripts/db_tools.sh restore backup_file.json  # Restore from specific backup
./scripts/db_tools.sh backup         # Create new backup
./scripts/db_tools.sh list           # List available backups
./scripts/db_tools.sh cleanup 5      # Keep only 5 most recent backups

# CRITICAL: Always use db_tools.sh for database operations
# This script handles proper data restoration with dependency ordering

# DEPRECATED/AVOID: The following scripts should NOT be used for regular database setup:
# - backend/populate_teams.py (uses hardcoded CSV paths)
# - backend/populate_teams_supabase.py (uses hardcoded CSV paths)

# User Administration (after users sign up)
cd backend && uv run python make_user_admin.py --list              # List all users
cd backend && uv run python make_user_admin.py --user-id USER_ID   # Make specific user admin
cd backend && uv run python make_user_admin.py --interactive       # Interactive mode

# Available admin scripts:
# - make_user_admin.py: Comprehensive user role management (RECOMMENDED)
# - create_admin_invite.py: Creates invitation codes for new admin users
# - reset_user_password.py: Reset user passwords in cloud environment

# Password Reset (Cloud Environment)
cd backend && uv run python reset_user_password.py --email "user@example.com" --password "newpassword" --confirm

# Note: tdrake13@gmail.com has been configured as an admin user
# Cleaned up: Removed redundant make_admin.py script (was hardcoded for tdrake13@gmail.com)
# Cleaned up: Removed redundant backup_database_supabase.py script (older version, use backup_database.py) 
# - backend/scripts/setup/populate_reference_data.py (creates sample data)
# - backend/scripts/sample-data/populate_sample_data.py (creates sample teams)
# These scripts are kept for reference but use db_tools.sh restore instead
```

## Environment Management

The application now supports multiple environments: **local**, **dev** (cloud), and **prod** (cloud).

### Environment Switching
```bash
# Switch environments
./switch-env.sh local    # Local Supabase (default)
./switch-env.sh dev      # Cloud development
./switch-env.sh prod     # Cloud production

# Check current environment
./switch-env.sh status

# Show help
./switch-env.sh help
```

### Environment Setup

#### 1. Local Environment (Default)
- Uses local Supabase instance
- Requires `npx supabase start`
- Best for e2e testing and offline development
- Configuration: `backend/.env.local`, `frontend/.env.local`

#### 2. Cloud Development Environment
- Uses Supabase cloud for cross-machine sync
- Perfect for match-scraper integration
- Configuration: `backend/.env.dev`, `frontend/.env.dev`

**Setup Cloud Dev Environment:**
```bash
# 1. Configure your cloud credentials
./setup-cloud-credentials.sh

# 2. Switch to dev environment
./switch-env.sh dev

# 3. Apply migrations to cloud database
npx supabase db push

# 4. Migrate your data
./scripts/db_tools.sh backup local    # Backup local data
./scripts/db_tools.sh restore dev     # Restore to cloud
```

#### 3. Production Environment
- Uses production Supabase project
- Configuration: `backend/.env.prod`, `frontend/.env.prod`
- Use with caution - production data

### Environment-Aware Database Operations

All database operations now support environment specification:

```bash
# Backup operations
./scripts/db_tools.sh backup         # Current environment
./scripts/db_tools.sh backup local   # Local environment
./scripts/db_tools.sh backup dev     # Cloud dev environment

# Restore operations
./scripts/db_tools.sh restore                    # Latest backup to current env
./scripts/db_tools.sh restore backup_file.json  # Specific backup to current env
./scripts/db_tools.sh restore backup_file.json dev  # Specific backup to dev env

# Reset operations (local only)
./scripts/db_tools.sh reset local    # Reset local database
```

### Development Workflows

#### Cross-Machine Development
```bash
# On Machine 1
./switch-env.sh dev              # Switch to cloud dev
./scripts/db_tools.sh backup     # Backup current state
./missing-table.sh start         # Develop with cloud database

# On Machine 2
./switch-env.sh dev              # Switch to cloud dev
./missing-table.sh start         # Access same cloud database
```

#### Match-Scraper Integration
```bash
# Setup stable cloud endpoint for match-scraper
./switch-env.sh dev                              # Switch to dev environment
./setup-cloud-credentials.sh                    # Configure cloud credentials
./missing-table.sh start                        # Start with cloud database

# Generate service account token for match-scraper
cd backend && uv run python create_service_account_token.py --service-name match-scraper --permissions manage_games
```

### Duplicate Game Cleanup

Interactive tool to find and clean up duplicate games using typer and rich:

```bash
# Scan for duplicates without making changes
cd backend && uv run python cleanup_duplicate_games.py scan

# Show database statistics
cd backend && uv run python cleanup_duplicate_games.py stats

# Preview what would be deleted (dry run)
cd backend && uv run python cleanup_duplicate_games.py clean --dry-run

# Interactive mode - review and choose what to delete
cd backend && uv run python cleanup_duplicate_games.py interactive

# Automatic cleanup (with backup)
cd backend && uv run python cleanup_duplicate_games.py clean --no-dry-run

# Export duplicates to JSON for analysis
cd backend && uv run python cleanup_duplicate_games.py scan --format json --save duplicates.json

# IMPORTANT: The tool identifies duplicates using the same criteria as database constraints:
# - For manual games: same teams, date, season, age group, game type, division
# - For external games: same match_id
# - Always keeps the newest game in each duplicate group by default
```

#### Testing Workflow
```bash
# Local testing (isolated)
./switch-env.sh local
npx supabase start
./scripts/db_tools.sh restore
./missing-table.sh start

# Cloud testing (shared)
./switch-env.sh dev
./missing-table.sh start
```

## Database Management Workflow

### Daily Development

#### Local Development
```bash
# Start local development
./switch-env.sh local
npx supabase start
./scripts/db_tools.sh restore    # Restore real data from latest backup

# Your development work...

# End of session (optional backup)
./scripts/db_tools.sh backup     # Create backup of current state
```

#### Cloud Development
```bash
# Start cloud development
./switch-env.sh dev
./missing-table.sh start         # No need to start Supabase - using cloud

# Your development work...

# End of session (optional backup)
./scripts/db_tools.sh backup dev # Create backup of current state
```

### Testing New Features
```bash
# Before major changes (environment-aware)
./scripts/db_tools.sh backup     # Create safety backup for current environment

# After testing, if things go wrong
./scripts/db_tools.sh restore    # Restore to last known good state

# Cross-environment testing
./scripts/db_tools.sh backup local      # Backup local state
./scripts/db_tools.sh restore dev       # Copy local data to dev for testing
```

### System Health Monitoring
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

# Login test setup (one-time)
cd backend && uv run python ../scripts/create_uptime_test_user.py  # Creates uptime_test@example.com user

# Standalone login test (requires backend dependencies)
cd backend && uv run python ../scripts/login_uptime_test.py       # Test just the login functionality
```

### Database Schema Changes
```bash
# 1. Backup current data
./scripts/db_tools.sh backup

# 2. Apply schema migrations
npx supabase db reset            # ONLY for schema changes

# 3. Restore real data
./scripts/db_tools.sh restore    # Restore from backup (data survives schema changes)
```

## Architecture

### Backend Structure
- **FastAPI application** in `backend/app.py`
- **Data Access Layer** using DAO pattern:
  - `backend/dao/enhanced_data_access_fixed.py` - Main data access
  - `backend/dao/local_data_access.py` - Local SQLite support
  - `backend/dao/supabase_data_access.py` - Supabase integration
- **Authentication** in `backend/auth.py` with JWT and role-based access (admin, team_manager, user)
- **Database migrations** in `supabase/migrations/`
- **Python dependencies** managed with `uv` (see `pyproject.toml`)

### Frontend Structure
- **Vue 3 application** with components in `frontend/src/components/`
- **Key components**:
  - `LeagueTable.vue` - Standings display
  - `ScoresSchedule.vue` - Games and schedules
  - `AdminPanel.vue` - Admin functionality
  - `AuthNav.vue`, `LoginForm.vue` - Authentication UI
- **State management** in `frontend/src/stores/`
- **Styling** with Tailwind CSS

### Database Schema
The application uses these main tables:
- `teams` - Team information with age group and division
- `games` - Game records with scores and dates
- `seasons` - Season definitions
- `age_groups` - Age group categories
- `divisions` - Division levels
- `user_profiles` - User data with roles

### API Endpoints
Key API routes in the backend:
- `/api/auth/*` - Authentication endpoints
- `/api/standings` - League standings data
- `/api/games` - Game schedules and scores
- `/api/teams` - Team information
- `/api/admin/*` - Admin operations

### Development Notes
- The project uses Python 3.13+ with `uv` for dependency management
- Frontend uses Vue 3 with Composition API
- Authentication is handled via Supabase Auth with custom role management
- The backend supports both Supabase (production) and SQLite (local development)
- Environment configuration switches between local and Supabase modes
- Docker setup available for containerized deployment

### Authentication Architecture

**✅ COMPLETED:** The application now uses a **backend-centered authentication architecture** that resolves Kubernetes networking issues.

**Authentication Flow:**
```
Frontend → Backend API → Supabase
```

**Key Endpoints:**
- `POST /api/auth/login` - User authentication with JWT tokens
- `POST /api/auth/signup` - User registration  
- `POST /api/auth/logout` - Session termination
- `POST /api/auth/refresh` - JWT token refresh
- `GET /api/auth/me` - Current user info
- `PUT /api/auth/profile` - Update user profile

**Benefits:**
- ✅ Resolves k8s networking issues (frontend pods can't reach external Supabase)
- ✅ Simplified Helm configuration (no frontend Supabase env vars needed)
- ✅ Better security (Supabase credentials only in backend)
- ✅ Consistent API-first architecture

### Current Branch
Working on `v1.4` branch with security features and deployment improvements.