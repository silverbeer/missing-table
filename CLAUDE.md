# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📚 Documentation First!

**CRITICAL**: This project maintains world-class documentation. When making changes, ALWAYS update relevant documentation.

### Documentation Structure

All documentation lives in `docs/` with clear organization:
- **[docs/README.md](docs/README.md)** - Master documentation hub (start here!)
- **[docs/01-getting-started/](docs/01-getting-started/)** - Setup and first contribution
- **[docs/02-development/](docs/02-development/)** - Daily workflows (THIS FILE'S CONTENT EXTRACTED HERE)
- **[docs/03-architecture/](docs/03-architecture/)** - System design
- **[docs/04-testing/](docs/04-testing/)** - Testing strategy
- **[docs/05-deployment/](docs/05-deployment/)** - Deployment guides
- **[docs/06-security/](docs/06-security/)** - Security practices
- **[docs/07-operations/](docs/07-operations/)** - Operations and maintenance
- **[docs/08-integrations/](docs/08-integrations/)** - External integrations
- **[docs/09-cicd/](docs/09-cicd/)** - CI/CD pipeline
- **[docs/10-contributing/](docs/10-contributing/)** - Contributing guides

### When to Update Documentation

**ALWAYS update docs when you**:
- Add a new feature → Update relevant guide + README.md
- Change a command or workflow → Update [docs/02-development/daily-workflow.md](docs/02-development/daily-workflow.md)
- Modify architecture → Update [docs/03-architecture/](docs/03-architecture/)
- Add/change tests → Update [docs/04-testing/](docs/04-testing/)
- Change deployment process → Update [docs/05-deployment/](docs/05-deployment/)
- Modify security → Update [docs/06-security/](docs/06-security/)

### Documentation Standards

Follow the standards in [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md):
- Use consistent formatting
- Include examples
- Keep it beginner-friendly
- Test all code examples
- Update "Last Updated" dates

**Remember**: Outdated docs are worse than no docs. Keep them current!

---

## 🚨 CRITICAL: Git Workflow - Protected Main Branch

**⚠️ NEVER COMMIT DIRECTLY TO MAIN ⚠️**

The `main` branch is **PROTECTED** and requires Pull Requests. Always follow this workflow:

### Required Git Workflow

```bash
# 1. Create a feature branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# 2. Make your changes and commit to feature branch
git add <files>
git commit -m "feat: your commit message"

# 3. Push feature branch
git push origin feature/your-feature-name

# 4. Create Pull Request via GitHub
# Go to: https://github.com/silverbeer/missing-table/pulls
# Click "New pull request"
# Select your feature branch
# Fill in PR description
# Request review

# 5. After PR approval and merge, delete feature branch
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

### Branch Protection Rules
- ❌ Cannot push directly to `main`
- ❌ Cannot force-push to `main`
- ✅ All changes must go through Pull Requests
- ✅ PRs trigger automated CI/CD pipelines

### Why This Matters
- **Code Review**: All changes reviewed before merging
- **CI/CD**: Automated testing and deployment workflows
- **Safety**: Prevents accidental breaking changes in production
- **Audit Trail**: Clear history of what changed and why

**Always create a feature branch first!**

---

## Project Overview

This is a full-stack web application for managing MLS Next sports league standings and match schedules. It uses FastAPI (Python 3.13+) for the backend and Vue 3 for the frontend, with Supabase as the primary database.

**For detailed information**, see:
- **Architecture**: [docs/03-architecture/README.md](docs/03-architecture/README.md)
- **Development Guide**: [docs/02-development/README.md](docs/02-development/README.md)
- **Complete Documentation**: [docs/README.md](docs/README.md)

## Key Commands

### Development

#### Service Management
```bash
# Primary service management script
./missing-table.sh dev      # Start with auto-reload (RECOMMENDED for development)
./missing-table.sh start    # Start both backend and frontend
./missing-table.sh stop     # Stop all running services
./missing-table.sh restart  # Restart all services
./missing-table.sh status   # Show service status and PIDs
./missing-table.sh logs     # View recent service logs (static)
./missing-table.sh tail     # Follow logs in real-time (Ctrl+C to stop)

# Development mode features:
# - Backend: Auto-reload on Python file changes (uvicorn --reload)
# - Frontend: Hot module replacement on Vue file changes (built-in)
# - No need to restart after code changes!

# Handles processes started by Claude or manually
# Logs stored in ~/.missing-table/logs/
# Works with both local and dev environments
# tail command supports both multitail and standard tail -f
```

#### Alternative Start Methods
```bash
# Frontend only (http://localhost:8080)
cd frontend && npm run serve

# Backend only (http://localhost:8000)
cd backend && uv run python app.py

# Run backend tests
cd backend && uv run pytest

# Lint frontend
cd frontend && npm run lint
```

### Docker Image Building

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

**Why this script is required:**
- GKE clusters run on AMD64 architecture
- Mac computers use ARM64 architecture
- Docker images must match the deployment platform
- Manual docker build commands often fail with "no match for platform" errors

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
- **build-and-push.sh**: Building images for cloud deployment (ALWAYS use this for GKE)
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

### Production Environment

The production environment is deployed to GKE with HTTPS and custom domain:
- **Production URL:** https://missingtable.com
- **Dev URL:** https://dev.missingtable.com
- **GKE Cluster:** `missing-table-prod` (production), `missing-table-dev` (development)
- **SSL:** Google-managed certificates (auto-renewing)
- **Database:** Supabase (separate production and dev projects)

#### Deployment Workflows

**Automated CI/CD:**
- **Feature branches → Dev:** Commits to feature branches automatically deploy to dev
- **Main branch → Production:** Merging PR to main automatically deploys to production
- **Automatic rollback:** Production deployments rollback automatically on failure
- **Versioning:** Semantic versioning with build IDs (e.g., v1.0.0-build.123)

**Key files:**
- `.github/workflows/deploy-dev.yml` - Auto-deploy to dev on feature branch push
- `.github/workflows/deploy-prod.yml` - Auto-deploy to prod on main branch push
- `VERSION` - Semantic version file (MAJOR.MINOR.PATCH)
- `scripts/version-bump.sh` - Bump version (major/minor/patch)
- `scripts/deploy-prod.sh` - Manual production deployment (emergency only)
- `scripts/health-check.sh` - Health check utility for all environments

#### Version Management

```bash
# Bump version
./scripts/version-bump.sh major    # 1.0.0 -> 2.0.0
./scripts/version-bump.sh minor    # 1.0.0 -> 1.1.0
./scripts/version-bump.sh patch    # 1.0.0 -> 1.0.1 (default)

# After bumping, commit and push to trigger deployment
git add VERSION
git commit -m "chore: bump version to $(cat VERSION)"
git push origin main  # Triggers production deployment
```

#### Health Checks

```bash
# Check dev environment
./scripts/health-check.sh dev

# Check production environment
./scripts/health-check.sh prod

# Check custom URL
./scripts/health-check.sh https://custom.example.com

# Interactive mode
./scripts/health-check.sh
```

#### Production Deployment

**Automated (Recommended):**
```bash
# 1. Create PR from feature branch
# 2. Review and approve PR
# 3. Merge to main - triggers automatic deployment
# 4. Monitor: https://github.com/silverbeer/missing-table/actions
```

**Manual (Emergency Only):**
```bash
# Interactive deployment
./scripts/deploy-prod.sh

# Deploy specific version
./scripts/deploy-prod.sh --version v1.2.3

# Rollback production
helm rollback missing-table -n missing-table-prod
```

**Documentation:**
- [Production Runbook](./docs/05-deployment/production-runbook.md) - Complete operations guide
- [Deployment Guide](./docs/05-deployment/README.md) - Deployment overview

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

**📖 For comprehensive migration guide, see [docs/MIGRATION_BEST_PRACTICES.md](docs/MIGRATION_BEST_PRACTICES.md)**

#### Quick Reference

```bash
# Supabase CLI (installed via Homebrew)
cd supabase-local
npx supabase start    # Start local Supabase
npx supabase stop     # Stop local Supabase
npx supabase status   # Check status and get URLs
```

#### Schema Migrations (NEW WORKFLOW - 2025-10-28)

**IMPORTANT**: All schema changes MUST be migrations. No ad-hoc SQL!

```bash
# Create new migration (preferred method - auto-generates SQL)
cd supabase-local
npx supabase db diff -f add_new_feature

# OR manually create migration file
npx supabase migration new add_new_feature

# Test migration locally
npx supabase db reset
cd .. && ./scripts/db_tools.sh restore

# Copy to official migrations directory
cp supabase-local/migrations/[timestamp]_*.sql supabase/migrations/

# Commit the migration
git add supabase/migrations/ supabase-local/migrations/
git commit -m "feat: add new feature migration"

# Deploy to dev
./switch-env.sh dev
cd supabase-local && npx supabase db push --linked

# Deploy to prod (after testing in dev)
./switch-env.sh prod
./scripts/db_tools.sh backup prod  # ALWAYS backup first!
cd supabase-local && npx supabase db push --linked
```

**Migration Files:**
- `supabase/migrations/` - Official migrations (single source of truth)
- `supabase-local/migrations/` - Working directory for creating/testing migrations
- `supabase/migrations/20251028000001_baseline_schema.sql` - Baseline (schema version 1.0.0)

**Schema Version:**
```sql
-- Check current schema version in any environment
SELECT * FROM get_schema_version();

-- View all version history
SELECT * FROM schema_version ORDER BY applied_at DESC;

-- Add version in new migration (at end of migration file)
SELECT add_schema_version('1.1.0', 'migration_name', 'Description');
```

**Best Practices:**
- ✅ Always test migrations locally before deploying
- ✅ Make migrations idempotent (safe to run multiple times)
- ✅ Backup before applying to production
- ✅ Use descriptive migration names
- ❌ Never modify existing migrations
- ❌ Never run ad-hoc SQL on databases

#### Database Backup & Restore

```bash
# Database backup and restore utility
./scripts/db_tools.sh restore        # Restore from latest backup (PREFERRED)
./scripts/db_tools.sh restore backup_file.json  # Restore from specific backup
./scripts/db_tools.sh backup         # Create new backup
./scripts/db_tools.sh list           # List available backups
./scripts/db_tools.sh cleanup 5      # Keep only 5 most recent backups

# CRITICAL: Always use db_tools.sh for database operations
# This script handles proper data restoration with dependency ordering

# IMPORTANT: Backups exclude user_profiles
# Users are managed separately per environment (see User Management section below)
# Backups only include: age_groups, divisions, match_types, seasons, teams, team_mappings, team_match_types, matches

# User Management (per environment)
# Users are NOT included in backups - manage separately in each environment
./scripts/setup_environment_users.sh local   # Setup test users for local dev
./scripts/setup_environment_users.sh dev     # Setup test users for cloud dev
./scripts/setup_environment_users.sh prod    # Setup admin users for production

# Or manually manage users with manage_users.py
cd backend && APP_ENV=prod uv run python manage_users.py create --email user@example.com --role admin
cd backend && APP_ENV=prod uv run python manage_users.py list
cd backend && APP_ENV=prod uv run python manage_users.py role --user user@example.com --role admin

# See docs/FOREIGN_KEY_DECISION.md for why users are managed separately
```

#### Database Inspector (Troubleshooting)

```bash
cd backend && uv run python inspect_db.py stats                      # Database statistics
cd backend && uv run python inspect_db.py teams                       # List all teams
cd backend && uv run python inspect_db.py teams --search IFA          # Search teams by name
cd backend && uv run python inspect_db.py age-groups                  # List age groups
cd backend && uv run python inspect_db.py divisions                   # List divisions
cd backend && uv run python inspect_db.py matches --limit 20          # List recent matches
cd backend && uv run python inspect_db.py matches --team IFA          # Filter by team
cd backend && uv run python inspect_db.py matches --age-group U14     # Filter by age group
cd backend && uv run python inspect_db.py matches --duplicates        # Find duplicate matches
cd backend && uv run python inspect_db.py match-detail 123            # Detailed match info
```

#### User Administration

```bash
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
```

#### Migration History

**Pre-Consolidation (Before 2025-10-28):**
- Had 50+ scattered SQL scripts across multiple directories
- Migrations split between `supabase/`, `supabase-local/`, `supabase-e2e/`
- Many ad-hoc SQL scripts that were never proper migrations

**Post-Consolidation (2025-10-28):**
- Single baseline migration consolidates all schema changes
- Clean migration workflow using Supabase CLI
- All future changes are incremental migrations
- Old migrations archived in `.archive/` directories for reference

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
cd backend && uv run python create_service_account_token.py --service-name match-scraper --permissions manage_matches
```

### Duplicate Match Cleanup

Interactive tool to find and clean up duplicate matches using typer and rich:

```bash
# Scan for duplicates without making changes
cd backend && uv run python cleanup_duplicate_matches.py scan

# Show database statistics
cd backend && uv run python cleanup_duplicate_matches.py stats

# Preview what would be deleted (dry run)
cd backend && uv run python cleanup_duplicate_matches.py clean --dry-run

# Interactive mode - review and choose what to delete
cd backend && uv run python cleanup_duplicate_matches.py interactive

# Automatic cleanup (with backup)
cd backend && uv run python cleanup_duplicate_matches.py clean --no-dry-run

# Export duplicates to JSON for analysis
cd backend && uv run python cleanup_duplicate_matches.py scan --format json --save duplicates.json

# IMPORTANT: The tool identifies duplicates using the same criteria as database constraints:
# - For manual matches: same teams, date, season, age group, match type, division
# - For external matches: same match_id
# - Always keeps the newest match in each duplicate group by default
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
  - `ScoresSchedule.vue` - Matches and schedules
  - `AdminPanel.vue` - Admin functionality
  - `AuthNav.vue`, `LoginForm.vue` - Authentication UI
- **State management** in `frontend/src/stores/`
- **Styling** with Tailwind CSS

### Database Schema
The application uses these main tables:
- `teams` - Team information with age group and division
- `matches` - Match records with scores and dates
- `seasons` - Season definitions
- `age_groups` - Age group categories
- `divisions` - Division levels
- `match_types` - Match type categories
- `team_match_types` - Team-specific match type assignments
- `user_profiles` - User data with roles

### API Endpoints
Key API routes in the backend:
- `/api/auth/*` - Authentication endpoints
- `/api/standings` - League standings data
- `/api/matches` - Match schedules and scores
- `/api/match-types` - Match type management
- `/api/teams` - Team information
- `/api/admin/*` - Admin operations

### Development Notes
- The project uses Python 3.13+ with `uv` for dependency management
- Frontend uses Vue 3 with Composition API
- Authentication is handled via Supabase Auth with custom role management
- The backend supports both Supabase (production) and SQLite (local development)
- Environment configuration switches between local and Supabase modes
- Docker setup available for containerized deployment

### RabbitMQ/Celery Distributed Messaging (In Progress)

**Status:** 🚀 Phase 0 Complete - Message queue infrastructure implementation

The application is being enhanced with a distributed messaging system using RabbitMQ and Celery to enable asynchronous processing of match data from the match-scraper.

**Architecture:** Hybrid deployment model
- **Cloud (GKE):** Frontend + Backend API ONLY (public services)
- **Local (K3s):** RabbitMQ + Celery Workers + Redis (private messaging infrastructure)

**Important:** Redis and Celery workers are NOT deployed to GKE to save costs and align with the hybrid architecture. These components run exclusively on your local K3s cluster (Rancher Desktop) in the `match-scraper` namespace.

**Implementation Tracking:**
- Feature Branch: `feature/rabbitmq-celery-integration`
- Documentation: [docs/rabbitmq-celery/README.md](docs/rabbitmq-celery/README.md)
- Current Phase: [Phase 0 - Repository Setup](docs/rabbitmq-celery/00-PHASE-0-SETUP.md) ✅
- Next Phase: Phase 1 - Message Queue Fundamentals

**Quick Commands:**
```bash
# Switch to local K3s cluster for messaging platform
kubectl config use-context rancher-desktop

# Switch to GKE for backend/frontend
kubectl config use-context gke_missing-table_us-central1_missing-table-dev

# Deploy messaging platform to match-scraper namespace
helm upgrade --install messaging-platform \
  ./helm/messaging-platform \
  --values ./helm/messaging-platform/values-local.yaml \
  -n match-scraper --create-namespace

# Verify deployment
kubectl get all -n match-scraper
```

**Benefits:**
- ✅ Asynchronous, non-blocking match data processing
- ✅ Automatic retries and error handling
- ✅ Distributed processing with easy scaling
- ✅ Full observability and monitoring
- ✅ Cost-effective ($5/month vs $72/month full GKE)

**Related Repositories:**
- [match-scraper](https://github.com/silverbeer/match-scraper) - Branch: `feature/rabbitmq-integration`

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

---

## 📖 Need More Information?

This file contains **quick reference commands only**. For comprehensive information:

### For Users/Contributors
- **Getting Started**: [docs/01-getting-started/README.md](docs/01-getting-started/README.md)
- **Contributing Guide**: [docs/10-contributing/README.md](docs/10-contributing/README.md)
- **For Students**: [docs/10-contributing/for-students.md](docs/10-contributing/for-students.md)

### For Developers
- **Daily Workflow**: [docs/02-development/daily-workflow.md](docs/02-development/daily-workflow.md)
- **Environment Management**: [docs/02-development/environment-management.md](docs/02-development/environment-management.md)
- **Architecture**: [docs/03-architecture/README.md](docs/03-architecture/README.md)
- **Testing**: [docs/04-testing/README.md](docs/04-testing/README.md)

### For DevOps
- **Deployment**: [docs/05-deployment/README.md](docs/05-deployment/README.md)
- **Security**: [docs/06-security/README.md](docs/06-security/README.md)
- **Operations**: [docs/07-operations/README.md](docs/07-operations/README.md)

### Master Hub
- **Complete Documentation**: [docs/README.md](docs/README.md) ⭐ Start here!

---

**Last Updated**: 2025-10-22
**Documentation Standards**: [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md)