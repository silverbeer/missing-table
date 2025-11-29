# Utility Scripts

This directory contains utility scripts for managing and validating the Missing Table backend.

## Available Scripts

### User Management
- **`create_test_user.py`** - Create a test non-admin user for testing role-based access
- **`create_admin_invite.py`** - Create admin invite directly in the database
- **`create_scraper_user.py`** - Create a service user for the match-scraper integration
- **`create_service_account_token.py`** - Generate JWT tokens for service accounts

### Validation & Verification
- **`validate_clubs.py`** - Validate clubs.json structure using Pydantic models
- **`validate_match_leagues.py`** - Validate that matches are assigned to the correct league
- **`verify_match_id.py`** - Verify that match_id column was added successfully to the games table

### Search & Data
- **`search_matches.py`** - CLI tool for searching matches with comprehensive filters
- **`delete_cross_source_duplicates.py`** - Delete duplicate matches from different sources
- **`cleanup_duplicate_matches.py`** - Interactive tool to find and clean up duplicate matches

## Usage

All scripts can be run from the backend root directory:

```bash
# From backend directory
uv run python scripts/utilities/search_matches.py --help
uv run python scripts/utilities/validate_match_leagues.py check
uv run python scripts/utilities/create_service_account_token.py --service-name match-scraper
uv run python scripts/utilities/cleanup_duplicate_matches.py scan
```

## Environment

Scripts automatically load environment variables from `.env` files in the backend root directory. The path resolution works from `scripts/utilities/` back to the backend root.

## Import Paths

All scripts that import from backend modules (like `dao.match_dao`, `models.clubs`, `auth`) have been configured to correctly resolve imports from the `scripts/utilities/` location.

