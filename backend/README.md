# Sports League Management Backend

A FastAPI-based backend for managing sports leagues, teams, games, and league tables.

## 📁 Project Structure

```
backend/
├── app.py                    # Main FastAPI application
├── app_sqlite.py            # SQLite fallback version
├── cli.py                   # Command-line interface
├── dao/                     # Data Access Objects
├── data/                    # Data files (SQLite DB, team lists)
├── docs/                    # Documentation
│   ├── CLI_USAGE.md
│   ├── MIGRATION_GUIDE.md
│   └── SUPABASE_SETUP.md
├── scripts/                 # Utility scripts
│   ├── migration/          # Database migration tools
│   ├── sample-data/        # Sample data generation
│   ├── setup/              # Database setup scripts
│   └── start/              # Startup scripts
├── sql/                     # SQL schema files
├── supabase-local/         # Local Supabase setup
└── tests/                  # Test files
```

## 🚀 Quick Start

### Option 1: Using Startup Scripts (Recommended)

```bash
cd backend
./scripts/start/start_supabase_cli.sh   # For Supabase CLI
# OR
./scripts/start/start_local.sh          # For local setup
```

### Option 2: Manual Start

```bash
cd backend
# Make sure environment variables are set
export SUPABASE_URL="http://127.0.0.1:54321"
export SUPABASE_SERVICE_KEY="<your_local_service_key>"

uv run python app.py
```

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Database Migration](#database-migration)
- [Running the Backend](#running-the-backend)
- [API Endpoints](#api-endpoints)
- [Development Tools](#development-tools)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13 or higher**
- **uv** (Modern Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
  - Replaces pip, venv, and virtualenv with faster, more reliable tooling
  - Automatically manages `pyproject.toml` and virtual environments
- **Supabase CLI** - Install via Homebrew: `brew install supabase/tap/supabase`
- **Docker** - Required for Supabase CLI local development

## Local Development Setup

### 1. Navigate to the Project Root

```bash
cd missing-table
```

### 2. Initialize Supabase CLI

```bash
supabase init
```

### 3. Start Supabase Local Services

```bash
supabase start
```

This will start all local Supabase services:
- PostgreSQL database on `localhost:54322`
- PostgREST API on `127.0.0.1:54321`
- Supabase Studio (admin UI) on `127.0.0.1:54323`

### 4. Install Backend Dependencies

```bash
cd backend
uv init --python 3.13
```

This creates a `pyproject.toml` file for modern Python dependency management.

**Install production dependencies:**
```bash
uv add fastapi uvicorn supabase httpx python-dotenv pydantic
```

**Install development dependencies:**
```bash
uv add --dev pytest httpx[testing] pytest-asyncio
```

All dependencies are managed in `pyproject.toml` with clear separation between production and development packages.

**Example pyproject.toml structure:**
```toml
[project]
name = "mls-standings-backend"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi",
    "uvicorn", 
    "supabase",
    "httpx",
    "python-dotenv",
    "pydantic"
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "httpx[testing]", 
    "pytest-asyncio"
]
```

### 5. Set Up Database Schema

The database schema is automatically applied via migrations when you run `supabase start`. The schema includes:

- `teams` - Team information and city
- `games` - Game results with team references
- `seasons` - Season periods (2023-2024, 2024-2025, etc.)
- `age_groups` - Age categories (U13, U14, etc.)
- `game_types` - Game types (League, Tournament, etc.)
- `team_mappings` - Many-to-many relationship between teams, age groups, and divisions
- `team_game_types` - Many-to-many relationship between teams and game types for participation tracking
- `user_profiles` - User authentication and role management

## Data Migration from SQLite

If you have existing SQLite data to migrate:

### 1. Ensure SQLite Database Exists

Make sure your `mlsnext_u13_fall.db` file is in the `backend/` directory.

### 2. Run Migration Script

```bash
cd backend
# Set up environment variables (or use .env.local)
export SUPABASE_URL="http://127.0.0.1:54321"
export SUPABASE_SERVICE_KEY="<your_local_service_key>"

uv run python migrate_sqlite_to_supabase_cli.py
```

**Note**: For local development, use the default Supabase CLI keys from your `.env.local` file.

This will:
- Read all teams and games from your SQLite database
- Migrate them to the local Supabase instance
- Associate teams with the U13 age group
- Set games to the 2024-2025 season

## Running the Backend

The backend uses `uv` for dependency management and automatically creates an isolated virtual environment based on `pyproject.toml`.

### Option 1: Using the Startup Script (Recommended)

```bash
cd backend
./start_supabase_cli.sh
```

### Option 2: Manual Start

```bash
cd backend
# Make sure environment variables are set
export SUPABASE_URL="http://127.0.0.1:54321"
export SUPABASE_SERVICE_KEY="<your_local_service_key>"

uv run python app.py
```

**Note:** `uv run` automatically:
- Creates and manages a virtual environment
- Installs dependencies from `pyproject.toml`
- Runs the application in the isolated environment

The backend will be running at **http://localhost:8000**

## API Endpoints

### Reference Data

- **GET `/api/age-groups`** - Get all age groups
- **GET `/api/seasons`** - Get all seasons  
- **GET `/api/current-season`** - Get the current active season
- **GET `/api/active-seasons`** - Get active seasons (current and future)
- **GET `/api/game-types`** - Get all game types
- **GET `/api/divisions`** - Get all divisions

### Teams

- **GET `/api/teams`** - Get teams (with optional filters)
  - Query parameters: `game_type_id`, `age_group_id`
- **POST `/api/teams`** - Add a new team
- **PUT `/api/teams/{team_id}`** - Update a team (admin only)
- **DELETE `/api/teams/{team_id}`** - Delete a team (admin only)

### Games

- **GET `/api/games`** - Get all games (with optional filters)
  - Query parameters: `season_id`, `age_group_id`, `division_id`, `game_type`
- **POST `/api/games`** - Add a new game
- **PUT `/api/games/{game_id}`** - Update a game (admin only)
- **DELETE `/api/games/{game_id}`** - Delete a game (admin only)
- **GET `/api/games/team/{team_id}`** - Get games for a specific team

### Authentication

- **POST `/api/auth/signup`** - User registration
- **POST `/api/auth/login`** - User login
- **POST `/api/auth/logout`** - User logout (requires auth)
- **GET `/api/auth/profile`** - Get user profile (requires auth)
- **PUT `/api/auth/profile`** - Update user profile (requires auth)
- **GET `/api/auth/users`** - Get all users (admin only)
- **PUT `/api/auth/users/role`** - Update user role (admin only)

### Admin CRUD Operations

- **Age Groups**: GET, POST, PUT, DELETE `/api/age-groups`
- **Seasons**: GET, POST, PUT, DELETE `/api/seasons` 
- **Divisions**: GET, POST, PUT, DELETE `/api/divisions`
- **Team Mappings**: POST, DELETE `/api/team-mappings`
- **Team Game Types**: POST, DELETE `/api/teams/{team_id}/game-types`

### League Table

- **GET `/api/table`** - Get league standings
  - Query parameters: `season_id`, `age_group_id`, `division_id`, `game_type`
  - Defaults: Current season, U14 age group, League games
  - Returns: Team standings with wins, draws, losses, goals, points

### Health Check

- **GET `/health`** - Backend health status

### Example Requests

```bash
# Get all teams
curl http://localhost:8000/api/teams

# Get league table for U13 2024-2025 season
curl http://localhost:8000/api/table

# Get games with filters
curl "http://localhost:8000/api/games?season_id=2&age_group_id=1"
```

## Development Tools

### Supabase Studio (Database Admin)

Access the database admin UI at: **http://127.0.0.1:54323**

- View and edit tables
- Run SQL queries
- Monitor database performance
- Manage users and permissions

### Supabase CLI Commands

```bash
# Check status of local services
supabase status

# Stop local services
supabase stop

# Reset database (applies all migrations)
supabase db reset

# View logs
supabase logs
```

### API Documentation

FastAPI automatically generates API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### Backend Won't Start

1. **Check if Supabase is running**:
   ```bash
   supabase status
   ```

2. **Restart Supabase if needed**:
   ```bash
   supabase stop
   supabase start
   ```

3. **Check environment variables**:
   ```bash
   echo $SUPABASE_URL
   echo $SUPABASE_SERVICE_KEY
   ```

### Database Connection Issues

1. **Verify Supabase CLI is running**:
   ```bash
   # Use your local anon key from .env.local
   curl http://127.0.0.1:54321/rest/v1/teams -H "apikey: $SUPABASE_ANON_KEY"
   ```

2. **Check Docker containers**:
   ```bash
   docker ps | grep supabase
   ```

### Empty API Responses

1. **Run migration script** to populate data from SQLite
2. **Check Supabase Studio** to verify data exists
3. **Restart backend** with proper environment variables

### Python/UV Issues

1. **Install UV** if not available:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Add missing dependencies**:
   ```bash
   # For production dependencies
   uv add <package-name>
   
   # For development dependencies  
   uv add --dev <package-name>
   ```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend      │    │   Supabase CLI  │
│  (Vue.js)       │◄──►│    (FastAPI)     │◄──►│  (PostgreSQL)   │
│  localhost:8081 │    │  localhost:8000  │    │ localhost:54321 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                │ Studio: :54323  │
                                                │ DB: :54322      │
                                                └─────────────────┘
```

- **Frontend**: Vue.js application serving the UI
- **Backend**: FastAPI REST API handling business logic
- **Database**: Local PostgreSQL via Supabase CLI
- **Admin UI**: Supabase Studio for database management

This setup provides a complete local development environment that mirrors the production Supabase setup while being easy to run and debug locally.