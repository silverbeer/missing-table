# Backend Directory Structure

This document outlines the organized structure of the backend directory and the async task processing architecture.

## 📁 Directory Layout

### Root Level - Core Application
- `app.py` - Main FastAPI application (current production version)
- `celery_app.py` - Celery worker for async task processing
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

## 🔄 Async Task Processing Architecture

### Overview

The backend uses **Celery** with **RabbitMQ** and **Redis** for async task processing, primarily for match submission from external sources (e.g., match-scraper).

### Components

```
┌─────────────────┐
│   FastAPI API   │  POST /api/matches/submit
│   (app.py)      │  GET /api/matches/task/{id}
└────────┬────────┘
         │ Queue Task
         ↓
┌─────────────────┐
│   RabbitMQ      │  Message Broker
│  (messaging ns) │  Queues tasks for workers
└────────┬────────┘
         │ Pick Task
         ↓
┌─────────────────┐
│ Celery Workers  │  Process tasks in parallel
│ (celery_app.py) │  2+ replicas in GKE
└────────┬────────┘
         │ Store Result
         ↓
┌─────────────────┐
│     Redis       │  Result Backend
│  (messaging ns) │  Stores task status
└─────────────────┘
```

### celery_app.py

The Celery worker handles async match submission:

**Key Features:**
- **Task**: `process_match_submission` - Creates/updates matches
- **Entity Resolution**: Automatically looks up team IDs, age groups, etc.
- **Deduplication**: Uses `external_match_id` to prevent duplicates
- **Error Handling**: Retries on transient failures
- **Logging**: Structured logging with context

**Task Flow:**
```python
1. Receive task from RabbitMQ queue
2. Parse match data (team names, not IDs)
3. Resolve entities:
   - Find/create teams by name
   - Lookup age group, division, season
   - Determine match type
4. Create or update match in database
5. Return result (match_id, status)
6. Store result in Redis
```

**Deployment:**
- Runs as separate pods in GKE (`missing-table-celery-worker`)
- Scales horizontally (currently 2 replicas)
- Shares codebase with FastAPI app (same Dockerfile)
- Started with: `celery -A celery_app worker --loglevel=info`

### API Endpoints

#### POST /api/matches/submit
Async match submission endpoint

**Request:**
```json
{
  "home_team": "IFA",
  "away_team": "NEFC",
  "match_date": "2025-10-15T14:00:00Z",
  "season": "2025-26",
  "age_group": "U14",
  "division": "Northeast",
  "match_status": "scheduled",
  "match_type": "League",
  "external_match_id": "mls-12345"
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/api/matches/task/550e8400...",
  "match": { "home_team": "IFA", ... }
}
```

#### GET /api/matches/task/{task_id}
Check async task status

**Response (Success):**
```json
{
  "task_id": "550e8400...",
  "state": "SUCCESS",
  "ready": true,
  "result": {
    "match_id": 489,
    "status": "created"
  }
}
```

### Infrastructure

**RabbitMQ** (`messaging` namespace):
- Message broker for Celery
- Default exchange for tasks
- Management UI: `localhost:15672`

**Redis** (`messaging` namespace):
- Result backend for task status
- Stores task results for polling
- Port: `6379`

**Monitoring:**
```bash
# Check workers
kubectl get pods -n missing-table-dev | grep celery-worker

# View worker logs
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker

# Check RabbitMQ
kubectl port-forward -n messaging svc/messaging-rabbitmq 15672:15672

# Check Redis
kubectl port-forward -n messaging svc/messaging-redis 6379:6379
```

### Benefits

✅ **Async Processing**: API responds immediately, processing happens in background
✅ **Scalability**: Add more Celery workers to handle increased load
✅ **Resilience**: Failed tasks can be retried automatically
✅ **Simplicity**: Match-scraper doesn't need to preload entity IDs
✅ **Monitoring**: Task status trackable via API

### Trade-offs

⚠️ **Complexity**: Additional infrastructure (RabbitMQ, Redis, Celery)
⚠️ **Eventual Consistency**: Match not immediately in database
⚠️ **Debugging**: Distributed system requires checking multiple logs

See: [Match-Scraper Integration Guide](../../08-integrations/match-scraper.md)

## 🧹 Maintenance

This structure was created to eliminate debugging clutter and provide clear organization. The `.gitignore` file has been updated to prevent future accumulation of temporary debugging files.

**Files Removed During Cleanup:**
- 12 debugging/temporary scripts (~57KB)
- Reduced clutter by 57%
- Organized remaining 23 files into logical directories

---

**Last Updated**: 2025-10-12 