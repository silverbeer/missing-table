# Database Schema Documentation

**Schema Version:** 1.1.0
**Last Updated:** 2025-10-30
**Environment:** All (Local, Dev, Production)

## Overview

This document describes the complete database schema for the Missing Table application. The schema is managed through Supabase migrations and includes support for multi-league sports organization.

## Schema Version History

| Version | Migration | Date | Description |
|---------|-----------|------|-------------|
| 1.0.0 | 20251028000001_baseline_schema | 2025-10-28 | Initial baseline schema consolidation |
| 1.1.0 | 20251029163754_add_league_layer | 2025-10-29 | Add league organizational layer above divisions |
| 1.2.0 | 20251030184100_add_parent_club_to_teams | 2025-10-30 | Add parent_club_id to teams for multi-league club support |

## Architecture Hierarchy

```
Club (Optional parent - New in v1.2.0)
  └── Team (e.g., "IFA Academy", "IFA Homegrown")
      └── League (via Division)
          └── Division
              └── Match

Alternative view:
League (New in v1.1.0)
  └── Division
      └── Team (can have parent_club_id - New in v1.2.0)
          └── Match
```

## Core Tables

### leagues (New in v1.1.0)

Top-level organizational structure for grouping divisions.

```sql
CREATE TABLE leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Fields:**
- `id` - Primary key
- `name` - Unique league name (e.g., "Homegrown", "MLS Next")
- `description` - Optional league description
- `is_active` - Whether league is currently active
- `created_at` - Record creation timestamp
- `updated_at` - Last update timestamp (auto-updated)

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE (name)`
- `idx_leagues_name ON (name)`

**RLS Policies:**
- `leagues_select_all` - Everyone can view leagues
- `leagues_admin_all` - Only admins can modify leagues

**Default Data:**
- "Homegrown" league created by default

---

### divisions

Divisions within a league (e.g., "Champions", "Premier I").

```sql
CREATE TABLE divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level INTEGER NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT divisions_name_league_id_key UNIQUE (name, league_id)
);
```

**Fields:**
- `id` - Primary key
- `name` - Division name (unique within league)
- `level` - Division level (1 = highest)
- `league_id` - Foreign key to leagues table (required, v1.1.0+)
- `created_at` - Record creation timestamp
- `updated_at` - Last update timestamp

**Key Changes in v1.1.0:**
- Added `league_id` column (required)
- Changed unique constraint from global `name` to `(name, league_id)`
- All existing divisions migrated to "Homegrown" league

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE (name, league_id)`
- `idx_divisions_league_id ON (league_id)`

**RLS Policies:**
- Everyone can view divisions
- Only admins can modify divisions

---

### age_groups

Age group categories (e.g., "U13", "U14", "U15").

```sql
CREATE TABLE age_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

### seasons

Season definitions with date ranges.

```sql
CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

### teams

Team information with organizational relationships and optional parent club hierarchy.

```sql
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    academy_team BOOLEAN DEFAULT false,
    parent_club_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,  -- NEW in v1.2.0
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Note: teams link to age_groups and divisions via team_mappings table
```

**Fields:**
- `id` - Primary key
- `name` - Team name (e.g., "IFA Academy", "IFA Homegrown")
- `city` - Team's city
- `academy_team` - Boolean flag for academy teams
- `parent_club_id` - Foreign key to parent club (NEW in v1.2.0, self-referencing)
- `created_at` - Record creation timestamp
- `updated_at` - Last update timestamp

**Key Changes in v1.2.0:**
- Added `parent_club_id` column for multi-league club support
- Enables clubs to have multiple teams (e.g., Academy and Homegrown)
- Self-referencing foreign key (teams can reference other teams as parent)
- Enforces single-level hierarchy (no grandparent relationships)

**Parent Club Hierarchy:**
```
IFA (parent_club_id: NULL) -- Parent club
  ├── IFA Academy (parent_club_id: points to IFA)
  └── IFA Homegrown (parent_club_id: points to IFA)
```

**Indexes:**
- `PRIMARY KEY (id)`
- `idx_teams_parent_club_id ON (parent_club_id)`
- `idx_teams_parent_club_age_group ON (parent_club_id, id) WHERE parent_club_id IS NOT NULL`

**Constraints:**
- `teams_parent_not_self` - A team cannot be its own parent
- Trigger `validate_parent_club_hierarchy` - Prevents circular references and enforces single-level hierarchy

**Helper Functions:**
- `get_club_teams(p_club_id)` - Returns all teams for a club (parent + children)
- `is_parent_club(p_team_id)` - Returns true if team has child teams
- `get_parent_club(p_team_id)` - Returns parent club information

**Views:**
- `teams_with_parent` - Convenient view showing teams with parent club information

**Important:**
- Teams are linked to leagues through `team_mappings` → `divisions` → `leagues`
- Parent club is optional (NULL for standalone teams)
- Only one level of hierarchy allowed (parent-child, no grandparents)

---

### matches

Match records with scores, dates, and status.

```sql
CREATE TABLE matches (
    id SERIAL PRIMARY KEY,
    home_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    home_score INTEGER,
    away_score INTEGER,
    match_date DATE NOT NULL,
    match_time TIME,
    location VARCHAR(255),
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE RESTRICT,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE RESTRICT,
    match_type_id INTEGER NOT NULL REFERENCES match_types(id) ON DELETE RESTRICT,
    division_id INTEGER NOT NULL REFERENCES divisions(id) ON DELETE RESTRICT,
    notes TEXT,
    status match_status DEFAULT 'scheduled',
    match_id VARCHAR(255),
    external_id VARCHAR(255),
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT matches_home_away_different CHECK (home_team_id != away_team_id),
    CONSTRAINT matches_scores_non_negative CHECK (
        (home_score IS NULL OR home_score >= 0) AND
        (away_score IS NULL OR away_score >= 0)
    ),

    -- Unique constraint for manual matches
    CONSTRAINT unique_manual_match UNIQUE NULLS NOT DISTINCT (
        home_team_id, away_team_id, match_date, season_id,
        age_group_id, match_type_id, division_id, match_id
    )
);
```

**Match Status Enum:**
```sql
CREATE TYPE match_status AS ENUM (
    'scheduled',
    'completed',
    'postponed',
    'cancelled',
    'tbd',
    'live'
);
```

**Important Notes:**
- `match_id` - External match identifier (used by match-scraper)
- `external_id` - Alternative external identifier
- `source` - Origin of match data (e.g., "match-scraper", "manual")
- Matches are linked to leagues through `divisions.league_id`

---

### match_types

Match type categories (e.g., "League", "Playoff", "Friendly").

```sql
CREATE TABLE match_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## Relationship Tables

### team_mappings

Maps external team names to internal team records.

```sql
CREATE TABLE team_mappings (
    id SERIAL PRIMARY KEY,
    external_name VARCHAR(255) NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_external_name_source UNIQUE (external_name, source)
);
```

---

### team_match_types

Defines which match types apply to each team.

```sql
CREATE TABLE team_match_types (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_type_id INTEGER NOT NULL REFERENCES match_types(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_team_match_type UNIQUE (team_id, match_type_id)
);
```

---

## Authentication Tables

### user_profiles

User information and roles.

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Roles:**
- `admin` - Full system access
- `team_manager` - Manage assigned teams
- `user` - View-only access

---

### team_manager_assignments

Assigns team managers to specific teams.

```sql
CREATE TABLE team_manager_assignments (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_team_assignment UNIQUE (user_id, team_id)
);
```

---

### invitations

Invitation codes for user registration.

```sql
CREATE TABLE invitations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL,
    max_uses INTEGER,
    current_uses INTEGER DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## Key Functions

### Authentication Functions

#### is_admin()

Returns true if the current user has admin role.

```sql
CREATE FUNCTION is_admin() RETURNS BOOLEAN
```

#### is_team_manager()

Returns true if the current user has team_manager role.

```sql
CREATE FUNCTION is_team_manager() RETURNS BOOLEAN
```

#### manages_team(p_team_id INTEGER)

Returns true if the current user manages the specified team.

```sql
CREATE FUNCTION manages_team(p_team_id INTEGER) RETURNS BOOLEAN
```

### Club/Team Functions (New in v1.2.0)

#### get_club_teams(p_club_id INTEGER)

Returns all teams for a club (parent club + all child teams).

```sql
CREATE FUNCTION get_club_teams(p_club_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    city VARCHAR(100),
    academy_team BOOLEAN,
    parent_club_id INTEGER,
    is_parent BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE
)
```

**Example:**
```sql
-- Get all IFA teams (parent + children)
SELECT * FROM get_club_teams(100);

-- Returns:
-- id: 100, name: "IFA", is_parent: true
-- id: 101, name: "IFA Academy", parent_club_id: 100, is_parent: false
-- id: 102, name: "IFA Homegrown", parent_club_id: 100, is_parent: false
```

#### is_parent_club(p_team_id INTEGER)

Returns true if the team is a parent club (has child teams).

```sql
CREATE FUNCTION is_parent_club(p_team_id INTEGER) RETURNS BOOLEAN
```

**Example:**
```sql
SELECT is_parent_club(100);  -- Returns true if team 100 has children
```

#### get_parent_club(p_team_id INTEGER)

Returns parent club information for a team (if exists).

```sql
CREATE FUNCTION get_parent_club(p_team_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    city VARCHAR(100)
)
```

**Example:**
```sql
-- Get parent club for IFA Academy
SELECT * FROM get_parent_club(101);
-- Returns: id: 100, name: "IFA", city: "Weymouth, MA"
```

### Schema Version Functions

#### get_schema_version()

Returns the current schema version.

```sql
CREATE FUNCTION get_schema_version()
RETURNS TABLE(version VARCHAR, applied_at TIMESTAMP WITH TIME ZONE, description TEXT)
```

#### add_schema_version()

Adds a new schema version record (used by migrations).

```sql
CREATE FUNCTION add_schema_version(
    p_version VARCHAR,
    p_migration_name VARCHAR,
    p_description TEXT DEFAULT NULL
)
RETURNS void
```

---

## Data Access Patterns

### Getting Teams by League

```sql
-- Get all teams in a specific league
SELECT t.*, d.league_id, l.name as league_name
FROM teams t
JOIN divisions d ON t.division_id = d.id
JOIN leagues l ON d.league_id = l.id
WHERE l.name = 'Homegrown';
```

### Getting Matches by League

```sql
-- Get all matches for a league
SELECT m.*, l.name as league_name
FROM matches m
JOIN divisions d ON m.division_id = d.id
JOIN leagues l ON d.league_id = l.id
WHERE l.name = 'Homegrown';
```

### Getting League Standings

```sql
-- Get standings for a league/division/age group
SELECT
    t.name as team_name,
    COUNT(m.id) as games_played,
    SUM(CASE
        WHEN m.home_team_id = t.id AND m.home_score > m.away_score THEN 3
        WHEN m.away_team_id = t.id AND m.away_score > m.home_score THEN 3
        WHEN m.home_score = m.away_score THEN 1
        ELSE 0
    END) as points
FROM teams t
JOIN divisions d ON t.division_id = d.id
JOIN leagues l ON d.league_id = l.id
LEFT JOIN matches m ON (m.home_team_id = t.id OR m.away_team_id = t.id)
    AND m.status = 'completed'
WHERE l.id = ? AND d.id = ? AND t.age_group_id = ?
GROUP BY t.id, t.name
ORDER BY points DESC;
```

---

## Migration Guide for match-scraper

### Key Changes in v1.1.0

1. **New `leagues` table** - Top-level organizational structure
2. **`divisions.league_id` column added** - All divisions now belong to a league
3. **Unique constraint change** - Division names are unique within a league (not globally)
4. **Default league** - "Homegrown" league created and all existing data migrated to it

### For External Systems (like match-scraper)

When creating/updating data:

1. **Divisions** - Must specify `league_id` when creating divisions
2. **Teams** - Teams are linked to leagues through `divisions.league_id`
3. **Matches** - Matches are linked to leagues through `divisions.league_id`

### Example: Creating a Match

```python
# match-scraper should continue using the same match creation logic
# The league association is handled automatically through division_id
match_data = {
    "home_team_id": 123,
    "away_team_id": 456,
    "match_date": "2025-10-30",
    "season_id": 1,
    "age_group_id": 2,
    "match_type_id": 1,
    "division_id": 3,  # This division has a league_id
    "match_id": "external_12345",
    "source": "match-scraper"
}
```

### Backward Compatibility

✅ **Fully backward compatible** - Existing code that doesn't query `leagues` directly will continue to work.

❌ **Breaking changes:**
- Division names are no longer globally unique (must be unique within a league)
- Cannot create divisions without a `league_id`

---

## Security (RLS Policies)

All tables have Row Level Security (RLS) enabled with policies:

- **Read Access** - All authenticated users can view data
- **Write Access** - Only admins can modify core tables
- **Team Managers** - Can modify matches/teams they manage
- **Users** - Can modify their own user_profiles

---

## References

- **Migration Files:** `supabase/migrations/`
- **Migration Guide:** `docs/MIGRATION_BEST_PRACTICES.md`
- **Architecture:** `docs/03-architecture/README.md`

---

**Last Updated:** 2025-10-30
**Schema Version:** 1.2.0
