"""
Database Schema Reference for match-scraper
============================================
Schema Version: 1.1.0
Last Updated: 2025-10-30

This module provides a reference for the Missing Table database schema
that can be imported by match-scraper or other external systems.
"""

# Schema Version
SCHEMA_VERSION = "1.1.0"
SCHEMA_DATE = "2025-10-30"

# ============================================================================
# TABLE DEFINITIONS
# ============================================================================

TABLES = {
    "leagues": {
        "description": "Top-level organizational structure (NEW in v1.1.0)",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(100) NOT NULL UNIQUE",
            "description": "TEXT",
            "is_active": "BOOLEAN DEFAULT true",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "indexes": ["name"],
        "unique_constraints": ["name"],
    },
    "divisions": {
        "description": "Divisions within a league",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(100) NOT NULL",
            "level": "INTEGER NOT NULL",
            "league_id": "INTEGER NOT NULL REFERENCES leagues(id)",  # NEW in v1.1.0
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "indexes": ["league_id"],
        "unique_constraints": ["(name, league_id)"],  # CHANGED in v1.1.0
        "foreign_keys": {
            "league_id": "leagues(id)",
        },
    },
    "age_groups": {
        "description": "Age group categories",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(50) NOT NULL UNIQUE",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "unique_constraints": ["name"],
    },
    "seasons": {
        "description": "Season definitions",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(100) NOT NULL UNIQUE",
            "start_date": "DATE NOT NULL",
            "end_date": "DATE NOT NULL",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "unique_constraints": ["name"],
    },
    "match_types": {
        "description": "Match type categories",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(50) NOT NULL UNIQUE",
            "description": "TEXT",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "unique_constraints": ["name"],
    },
    "teams": {
        "description": "Team information",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "name": "VARCHAR(100) NOT NULL",
            "age_group_id": "INTEGER NOT NULL REFERENCES age_groups(id)",
            "division_id": "INTEGER NOT NULL REFERENCES divisions(id)",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "indexes": ["age_group_id", "division_id"],
        "unique_constraints": ["(name, age_group_id, division_id)"],
        "foreign_keys": {
            "age_group_id": "age_groups(id)",
            "division_id": "divisions(id)",
        },
    },
    "matches": {
        "description": "Match records",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "home_team_id": "INTEGER NOT NULL REFERENCES teams(id)",
            "away_team_id": "INTEGER NOT NULL REFERENCES teams(id)",
            "home_score": "INTEGER",
            "away_score": "INTEGER",
            "match_date": "DATE NOT NULL",
            "match_time": "TIME",
            "location": "VARCHAR(255)",
            "season_id": "INTEGER NOT NULL REFERENCES seasons(id)",
            "age_group_id": "INTEGER NOT NULL REFERENCES age_groups(id)",
            "match_type_id": "INTEGER NOT NULL REFERENCES match_types(id)",
            "division_id": "INTEGER NOT NULL REFERENCES divisions(id)",
            "notes": "TEXT",
            "status": "match_status DEFAULT 'scheduled'",
            "match_id": "VARCHAR(255)",  # External match identifier
            "external_id": "VARCHAR(255)",  # Alternative external identifier
            "source": "VARCHAR(100)",  # Origin of match data (e.g., 'match-scraper')
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "indexes": [
            "home_team_id",
            "away_team_id",
            "season_id",
            "age_group_id",
            "division_id",
            "match_date",
            "status",
            "match_id",
        ],
        "unique_constraints": [
            "(home_team_id, away_team_id, match_date, season_id, age_group_id, match_type_id, division_id, match_id)"
        ],
        "foreign_keys": {
            "home_team_id": "teams(id)",
            "away_team_id": "teams(id)",
            "season_id": "seasons(id)",
            "age_group_id": "age_groups(id)",
            "match_type_id": "match_types(id)",
            "division_id": "divisions(id)",
        },
    },
    "team_mappings": {
        "description": "Maps external team names to internal team records",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "external_name": "VARCHAR(255) NOT NULL",
            "team_id": "INTEGER NOT NULL REFERENCES teams(id)",
            "source": "VARCHAR(100)",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "indexes": ["external_name", "team_id"],
        "unique_constraints": ["(external_name, source)"],
        "foreign_keys": {
            "team_id": "teams(id)",
        },
    },
    "team_match_types": {
        "description": "Defines which match types apply to each team",
        "columns": {
            "id": "SERIAL PRIMARY KEY",
            "team_id": "INTEGER NOT NULL REFERENCES teams(id)",
            "match_type_id": "INTEGER NOT NULL REFERENCES match_types(id)",
            "created_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        },
        "unique_constraints": ["(team_id, match_type_id)"],
        "foreign_keys": {
            "team_id": "teams(id)",
            "match_type_id": "match_types(id)",
        },
    },
}

# ============================================================================
# ENUMS
# ============================================================================

ENUMS = {
    "match_status": ["scheduled", "completed", "postponed", "cancelled", "tbd", "live"]
}

# ============================================================================
# REQUIRED FIELDS FOR MATCH CREATION
# ============================================================================

REQUIRED_MATCH_FIELDS = [
    "home_team_id",
    "away_team_id",
    "match_date",
    "season_id",
    "age_group_id",
    "match_type_id",
    "division_id",
]

OPTIONAL_MATCH_FIELDS = [
    "home_score",
    "away_score",
    "match_time",
    "location",
    "notes",
    "status",
    "match_id",  # Recommended for external systems
    "external_id",
    "source",  # Recommended: set to 'match-scraper'
]

# ============================================================================
# DATA HIERARCHY
# ============================================================================

DATA_HIERARCHY = """
League (NEW in v1.1.0)
  └── Division
      └── Team
          └── Match
"""

# ============================================================================
# MIGRATION NOTES FOR MATCH-SCRAPER
# ============================================================================

MIGRATION_NOTES = """
KEY CHANGES IN v1.1.0:
=====================

1. NEW TABLE: 'leagues'
   - Top-level organizational structure
   - Contains columns: id, name, description, is_active

2. MODIFIED TABLE: 'divisions'
   - Added column: league_id (REQUIRED, references leagues.id)
   - Changed unique constraint: name is now unique within league (not globally)
   - Old: UNIQUE (name)
   - New: UNIQUE (name, league_id)

3. DEFAULT DATA:
   - "Homegrown" league created by default
   - All existing divisions migrated to "Homegrown" league

IMPACT ON MATCH-SCRAPER:
========================

✅ NO CHANGES NEEDED for existing match creation code
   - Continue using the same fields: home_team_id, away_team_id, division_id, etc.
   - League association happens automatically through divisions.league_id

✅ BACKWARD COMPATIBLE for match/team queries
   - Teams are automatically linked to leagues via division_id
   - No breaking changes to existing queries

❌ BREAKING CHANGES if creating divisions:
   - Must specify league_id when creating new divisions
   - Division names no longer globally unique

EXAMPLE MATCH CREATION (unchanged):
===================================

match_data = {
    "home_team_id": 123,
    "away_team_id": 456,
    "match_date": "2025-10-30",
    "season_id": 1,
    "age_group_id": 2,
    "match_type_id": 1,
    "division_id": 3,  # This division already has a league_id
    "match_id": "external_12345",
    "source": "match-scraper",
    "status": "scheduled"
}

# POST to: /api/matches
# Or INSERT directly into matches table
"""

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def get_required_fields(table_name: str) -> list:
    """Get list of required fields for a table"""
    if table_name == "matches":
        return REQUIRED_MATCH_FIELDS
    # Add other tables as needed
    return []


def get_optional_fields(table_name: str) -> list:
    """Get list of optional fields for a table"""
    if table_name == "matches":
        return OPTIONAL_MATCH_FIELDS
    # Add other tables as needed
    return []


def get_table_info(table_name: str) -> dict:
    """Get complete information about a table"""
    return TABLES.get(table_name, {})


def validate_match_data(match_data: dict) -> tuple[bool, list]:
    """
    Validate match data dictionary.
    Returns: (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    for field in REQUIRED_MATCH_FIELDS:
        if field not in match_data:
            errors.append(f"Missing required field: {field}")

    # Check data types and constraints
    if "home_team_id" in match_data and "away_team_id" in match_data:
        if match_data["home_team_id"] == match_data["away_team_id"]:
            errors.append("home_team_id and away_team_id must be different")

    if "home_score" in match_data and match_data["home_score"] is not None:
        if match_data["home_score"] < 0:
            errors.append("home_score cannot be negative")

    if "away_score" in match_data and match_data["away_score"] is not None:
        if match_data["away_score"] < 0:
            errors.append("away_score cannot be negative")

    if "status" in match_data:
        if match_data["status"] not in ENUMS["match_status"]:
            errors.append(
                f"Invalid status. Must be one of: {', '.join(ENUMS['match_status'])}"
            )

    return len(errors) == 0, errors


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print(f"Missing Table Database Schema v{SCHEMA_VERSION}")
    print(f"Last Updated: {SCHEMA_DATE}\n")

    print("Available Tables:")
    for table_name, table_info in TABLES.items():
        print(f"  - {table_name}: {table_info['description']}")

    print("\nData Hierarchy:")
    print(DATA_HIERARCHY)

    print("\nMigration Notes:")
    print(MIGRATION_NOTES)

    # Example validation
    example_match = {
        "home_team_id": 123,
        "away_team_id": 456,
        "match_date": "2025-10-30",
        "season_id": 1,
        "age_group_id": 2,
        "match_type_id": 1,
        "division_id": 3,
        "match_id": "external_12345",
        "source": "match-scraper",
        "status": "scheduled",
    }

    is_valid, errors = validate_match_data(example_match)
    print(f"\nExample Match Validation: {'✓ Valid' if is_valid else '✗ Invalid'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
