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

### Docker
```bash
docker-compose up     # Start all services
docker-compose down   # Stop all services
docker-compose build  # Rebuild images
```

### Database/Supabase
```bash
npx supabase start    # Start local Supabase
npx supabase stop     # Stop local Supabase
npx supabase status   # Check status and get URLs
npx supabase db reset # Reset database
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

### Current Branch
Working on `v1.1` branch with authentication and admin features in progress.