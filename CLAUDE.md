# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack web application for managing MLS Next sports league standings and game schedules. It uses FastAPI (Python 3.13+) for the backend and Vue 3 for the frontend, with Supabase as the primary database.

## Key Commands

### Development
```bash
# Start both frontend and backend
./start.sh

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

### Database/Supabase
```bash
npx supabase start    # Start local Supabase
npx supabase stop     # Stop local Supabase
npx supabase status   # Check status and get URLs

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

# Note: tdrake13@gmail.com has been configured as an admin user
# Cleaned up: Removed redundant make_admin.py script (was hardcoded for tdrake13@gmail.com)
# Cleaned up: Removed redundant backup_database_supabase.py script (older version, use backup_database.py) 
# - backend/scripts/setup/populate_reference_data.py (creates sample data)
# - backend/scripts/sample-data/populate_sample_data.py (creates sample teams)
# These scripts are kept for reference but use db_tools.sh restore instead
```

## Database Management Workflow

### Daily Development
```bash
# Start development
npx supabase start
./scripts/db_tools.sh restore    # Restore real data from latest backup

# Your development work...

# End of session (optional backup)
./scripts/db_tools.sh backup     # Create backup of current state
```

### Testing New Features
```bash
# Before major changes
./scripts/db_tools.sh backup     # Create safety backup

# After testing, if things go wrong
./scripts/db_tools.sh restore    # Restore to last known good state
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