# Backend Directory Structure

This document outlines the organized structure of the backend directory.

## 📁 Directory Layout

### Root Level - Core Application
- `app.py` - Main FastAPI application (current production version)
- `app_sqlite.py` - SQLite fallback version for local development
- `cli.py` - Command-line interface for database operations
- `pyproject.toml` - Python project configuration and dependencies
- `Dockerfile` - Docker container configuration

### `/dao/` - Data Access Objects
Contains all database connection and data access logic:
- `enhanced_data_access_fixed.py` - Main Supabase connection (current)
- `local_data_access.py` - Local development data access
- `supabase_data_access.py` - Original Supabase implementation
- `data_access.py` - SQLite data access

### `/data/` - Data Files
- `mlsnext_u13_fall.db` - SQLite database with sample data
- `teams.txt` - List of team names

### `/docs/` - Documentation
- `CLI_USAGE.md` - Command-line interface documentation
- `MIGRATION_GUIDE.md` - Database migration instructions
- `SUPABASE_SETUP.md` - Supabase setup guide

### `/scripts/` - Utility Scripts

#### `/scripts/migration/` - Database Migration
- `migrate_sqlite_to_supabase_cli.py` - Migrate from SQLite to Supabase CLI
- `migrate_to_new_supabase.py` - Comprehensive migration tool

#### `/scripts/setup/` - Database Setup
- `create_supabase_schema.py` - Create database schema
- `setup_schema.py` - Schema setup utility
- `populate_reference_data.py` - Populate reference tables

#### `/scripts/sample-data/` - Sample Data Generation
- `create_sample_games.py` - Generate sample games
- `populate_sample_data.py` - Populate sample data

#### `/scripts/start/` - Startup Scripts
- `start_supabase_cli.sh` - Start with Supabase CLI
- `start_local.sh` - Start with local setup

### `/sql/` - SQL Schema Files
- `generate_supabase_schema.sql` - Generated schema
- `supabase_schema.sql` - Base schema definition

### `/supabase-local/` - Local Supabase Setup
- `docker-compose.yml` - Local Supabase Docker setup
- `setup_local_supabase.py` - Local Supabase configuration

### `/tests/` - Test Files
- `test_e2e_supabase.py` - End-to-end Supabase tests
- `test_dao.py` - Data access object tests

## 🚀 Usage Examples

### Starting the Application
```bash
# Using startup scripts (recommended)
./scripts/start/start_supabase_cli.sh

# Manual start
uv run python app.py
```

### Running Migrations
```bash
# Migrate from SQLite to Supabase CLI
uv run python scripts/migration/migrate_sqlite_to_supabase_cli.py

# Setup reference data
uv run python scripts/setup/populate_reference_data.py
```

### Running Tests
```bash
# End-to-end tests
uv run python tests/test_e2e_supabase.py

# CLI interface
uv run python cli.py list-teams
```

## 🧹 Maintenance

This structure was created to eliminate debugging clutter and provide clear organization. The `.gitignore` file has been updated to prevent future accumulation of temporary debugging files.

**Files Removed During Cleanup:**
- 12 debugging/temporary scripts (~57KB)
- Reduced clutter by 57%
- Organized remaining 23 files into logical directories 