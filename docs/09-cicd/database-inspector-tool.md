# Database Inspector Tool

**Date**: 2025-10-08
**Status**: Completed
**File**: backend/inspect_db.py

## Overview

A powerful CLI tool for inspecting and troubleshooting database data directly via Supabase, bypassing the backend DAOs. This tool provides quick access to view, filter, and identify data issues like duplicates and incorrect age group assignments.

## Features

- **Direct Database Access**: Connects directly to Supabase, bypassing backend DAOs for raw data inspection
- **Environment Aware**: Automatically loads `.env.{APP_ENV}` files (local/dev/prod)
- **Rich Terminal UI**: Beautiful tables and panels using the `rich` library
- **Comprehensive Commands**: Browse age groups, divisions, teams, games with filtering
- **Duplicate Detection**: Identifies duplicate games based on key criteria
- **Detailed Inspection**: Deep-dive into individual game records

## Installation

The tool uses `typer` and `rich` which are included in the backend dependencies:

```bash
cd backend
uv sync  # Ensure dependencies are installed
```

## Usage

### Database Statistics

```bash
cd backend && uv run python inspect_db.py stats
```

Shows counts for teams, games, age groups, divisions, and seasons.

### Browse Teams

```bash
# List all teams
cd backend && uv run python inspect_db.py teams

# Search teams by name
cd backend && uv run python inspect_db.py teams --search IFA

# Verbose output with additional details
cd backend && uv run python inspect_db.py teams --verbose
```

### Browse Age Groups

```bash
cd backend && uv run python inspect_db.py age-groups
```

### Browse Divisions

```bash
cd backend && uv run python inspect_db.py divisions
```

### Browse Games

```bash
# List recent games (default limit: 50)
cd backend && uv run python inspect_db.py games

# Increase limit
cd backend && uv run python inspect_db.py games --limit 100

# Filter by team name
cd backend && uv run python inspect_db.py games --team IFA

# Filter by age group
cd backend && uv run python inspect_db.py games --age-group U14

# Filter by season
cd backend && uv run python inspect_db.py games --season 2025-2026

# Combine filters
cd backend && uv run python inspect_db.py games --team IFA --age-group U14
```

### Find Duplicate Games

```bash
cd backend && uv run python inspect_db.py games --duplicates
```

**Duplicate Detection Criteria:**
- Same game date
- Same home and away teams
- Same season
- Same game type

This helps identify games that were imported multiple times or have data quality issues.

### Game Details

```bash
cd backend && uv run python inspect_db.py game-detail <GAME_ID>
```

Shows comprehensive information about a specific game including:
- Game metadata (ID, date, status, source)
- Team information (home/away with IDs)
- Score
- Competition details (season, age group, division, game type)
- Creation/update timestamps
- Match ID (for external games)

**Example:**
```bash
cd backend && uv run python inspect_db.py game-detail 473
```

## Environment Management

The tool automatically loads environment variables from `.env.{APP_ENV}` files:

```bash
# Use with local database
export APP_ENV=local
cd backend && uv run python inspect_db.py stats

# Use with dev database
export APP_ENV=dev
cd backend && uv run python inspect_db.py stats

# Use with prod database (use caution!)
export APP_ENV=prod
cd backend && uv run python inspect_db.py stats
```

Or use the environment switcher:
```bash
./switch-env.sh dev
cd backend && uv run python inspect_db.py games --team IFA
```

## Use Cases

### 1. Investigating Duplicate Games

**Problem**: User sees duplicate U14 IFA games, suspects one is actually a U13 game.

**Solution:**
```bash
# Find all IFA games
cd backend && uv run python inspect_db.py games --team IFA --age-group U14

# Check for duplicates
cd backend && uv run python inspect_db.py games --team IFA --duplicates

# Inspect specific game details
cd backend && uv run python inspect_db.py game-detail 473
```

### 2. Verifying Age Group Assignments

**Problem**: Match-scraper may have assigned wrong age group to games.

**Solution:**
```bash
# List all games for a team across all age groups
cd backend && uv run python inspect_db.py games --team "IFA"

# Check specific age group
cd backend && uv run python inspect_db.py games --team "IFA" --age-group U13
```

### 3. Data Quality Auditing

**Problem**: Need to verify data consistency across environments.

**Solution:**
```bash
# Compare statistics
./switch-env.sh local && cd backend && uv run python inspect_db.py stats
./switch-env.sh dev && cd backend && uv run python inspect_db.py stats

# Find all duplicates in production
./switch-env.sh prod && cd backend && uv run python inspect_db.py games --duplicates
```

### 4. Debugging Import Issues

**Problem**: Games imported from external source have issues.

**Solution:**
```bash
# Filter by source
cd backend && uv run python inspect_db.py games --limit 100 | grep "import"

# Check specific season
cd backend && uv run python inspect_db.py games --season "2025-2026"
```

## Technical Details

### Direct Supabase Connection

The tool creates its own Supabase client using credentials from environment files:

```python
def get_supabase_client() -> Client:
    """Get direct Supabase client (bypassing DAOs)"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return create_client(url, key)
```

### Environment Loading

```python
def load_environment():
    """Load environment variables from .env file based on APP_ENV"""
    app_env = os.getenv("APP_ENV", "local")
    env_file = Path(__file__).parent / f".env.{app_env}"
    load_dotenv(env_file)
    return app_env
```

## Command Reference

| Command | Description | Common Options |
|---------|-------------|----------------|
| `stats` | Show database statistics | None |
| `age-groups` | List all age groups | `--verbose` |
| `divisions` | List all divisions | `--verbose` |
| `teams` | List teams | `--search`, `--verbose` |
| `games` | List games | `--team`, `--age-group`, `--season`, `--duplicates`, `--limit` |
| `game-detail` | Show game details | `<GAME_ID>` (required) |

## Related Tools

- **db_tools.sh**: Database backup/restore operations
- **cleanup_duplicate_games.py**: Interactive duplicate cleanup tool
- **missing-table.sh**: Service management with database status

## Troubleshooting

### Connection Issues

If you see connection errors:
1. Check that your `.env.{APP_ENV}` file exists
2. Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set
3. For local: ensure Supabase is running (`npx supabase start`)

### No Data Returned

If queries return no results:
1. Check you're connected to the right environment (`./switch-env.sh status`)
2. Verify data exists (`uv run python inspect_db.py stats`)
3. Check filter criteria (age group name must match exactly)

### Schema Errors

If you see relationship errors:
1. The database schema may have changed
2. Check the actual schema with: `npx supabase db diff`
3. Update the tool's queries to match current schema

## Future Enhancements

Consider adding:
- Export to CSV/JSON for offline analysis
- Bulk update commands (change age group, fix duplicates)
- Data validation rules (check for missing required fields)
- Integration with cleanup_duplicate_games.py
- Visualization of game distributions by age group/division

---

**Last Updated**: 2025-10-08
**Author**: Claude Code
**Related Files**:
- `backend/inspect_db.py`
- `CLAUDE.md` (usage examples)
