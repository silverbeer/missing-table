# Database Schema Export for match-scraper

This directory contains the latest database schema exports for external systems like `match-scraper`.

## 📦 Available Files

### 1. **database-schema.md** (Recommended)
- **Format:** Markdown documentation
- **Best for:** Human-readable reference, documentation
- **Contains:**
  - Complete schema documentation
  - Data hierarchy diagrams
  - Query examples
  - Migration notes
  - Backward compatibility information

### 2. **database-schema.sql**
- **Format:** SQL DDL statements
- **Best for:** Schema inspection, SQL-based tools
- **Contains:**
  - Complete CREATE TABLE statements
  - All indexes and constraints
  - Quick reference comments for match-scraper

### 3. **database-schema.py**
- **Format:** Python module
- **Best for:** Programmatic access, validation
- **Contains:**
  - Schema definitions as Python dictionaries
  - Helper functions for validation
  - Required/optional field lists
  - Example usage

## 🚀 Quick Start for match-scraper

### Option 1: Copy to match-scraper repo

```bash
# Copy all schema files to match-scraper
cp docs/database-schema.* /path/to/match-scraper/docs/

# Or just the markdown
cp docs/database-schema.md /path/to/match-scraper/MISSING_TABLE_SCHEMA.md
```

### Option 2: Reference via Git

```bash
# In match-scraper repo, add as a reference
curl -o MISSING_TABLE_SCHEMA.md \
  https://raw.githubusercontent.com/silverbeer/missing-table/feature/add-league-layer/docs/database-schema.md
```

### Option 3: Import Python module

```python
# Copy database-schema.py to match-scraper
# Then import and use:

from database_schema import (
    SCHEMA_VERSION,
    REQUIRED_MATCH_FIELDS,
    OPTIONAL_MATCH_FIELDS,
    validate_match_data,
    MIGRATION_NOTES
)

# Validate match data before sending
match_data = {
    "home_team_id": 123,
    "away_team_id": 456,
    "match_date": "2025-10-30",
    "season_id": 1,
    "age_group_id": 2,
    "match_type_id": 1,
    "division_id": 3,
    "match_id": "external_12345",
    "source": "match-scraper",
}

is_valid, errors = validate_match_data(match_data)
if not is_valid:
    print(f"Validation errors: {errors}")
```

## 📋 Schema Version Information

- **Current Version:** 1.1.0
- **Last Updated:** 2025-10-30
- **Major Changes:**
  - Added `leagues` table (top-level organization)
  - Added `divisions.league_id` column (REQUIRED)
  - Changed division name uniqueness (now unique within league)
  - Created default "Homegrown" league

## ✅ Impact on match-scraper

### Good News: Mostly Backward Compatible!

✅ **NO CHANGES NEEDED** for existing match creation code
- Continue using the same API endpoints
- Same required fields: `home_team_id`, `away_team_id`, `division_id`, etc.
- League association happens automatically through `division_id`

✅ **AUTOMATIC** league linkage
- All teams automatically linked to leagues via divisions
- No need to query or specify league_id when creating matches

### What Changed

❌ **BREAKING if creating divisions:**
- Must specify `league_id` when creating new divisions
- Division names no longer globally unique (unique within league)

### Example (unchanged)

```python
# This code still works exactly the same!
match_data = {
    "home_team_id": 123,
    "away_team_id": 456,
    "match_date": "2025-10-30",
    "season_id": 1,
    "age_group_id": 2,
    "match_type_id": 1,
    "division_id": 3,  # This division already has league_id
    "match_id": "external_12345",
    "source": "match-scraper",
    "status": "scheduled"
}

# POST to missing-table API
requests.post("https://dev.missingtable.com/api/matches", json=match_data)
```

## 🔍 Key Schema Relationships

```
League (NEW)
  └── Division (now has league_id)
      ├── Team (unchanged)
      │   └── Match (unchanged)
      └── Match (unchanged - links via division_id)
```

## 📚 Detailed Documentation

For complete details, see:
- **database-schema.md** - Full documentation with examples
- **database-schema.sql** - SQL schema reference
- **database-schema.py** - Python validation module

## 🤝 Integration Checklist

For match-scraper integration:

- [ ] Copy schema documentation to match-scraper repo
- [ ] Review migration notes in `database-schema.md`
- [ ] Confirm existing match creation code still works
- [ ] Update match-scraper docs to reference schema version 1.1.0
- [ ] (Optional) Add Python validation module for data validation
- [ ] Test against dev environment: https://dev.missingtable.com

## 📞 Questions?

If you have questions about the schema changes:
1. Check `database-schema.md` for detailed documentation
2. Review migration file: `supabase/migrations/20251029163754_add_league_layer.sql`
3. See main docs: `docs/03-architecture/README.md`

## 🔄 Keeping Schema in Sync

To get the latest schema in the future:

```bash
# Pull latest from missing-table repo
cd /path/to/missing-table
git pull origin main

# Copy updated schema docs
cp docs/database-schema.* /path/to/match-scraper/docs/
```

Or set up a Git submodule/subtree for automatic updates.

---

**Schema Version:** 1.1.0
**Last Updated:** 2025-10-30
**Branch:** feature/add-league-layer
**Status:** Ready for integration
