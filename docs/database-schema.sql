-- ============================================================================
-- MISSING TABLE DATABASE SCHEMA EXPORT
-- ============================================================================
-- Schema Version: 1.1.0
-- Last Updated: 2025-10-30
-- Purpose: Complete schema reference for external systems (e.g., match-scraper)
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE match_status AS ENUM (
    'scheduled',
    'completed',
    'postponed',
    'cancelled',
    'tbd',
    'live'
);

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Leagues (New in v1.1.0)
CREATE TABLE leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Age Groups
CREATE TABLE age_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seasons
CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Divisions (Updated in v1.1.0 - added league_id)
CREATE TABLE divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level INTEGER NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT divisions_name_league_id_key UNIQUE (name, league_id)
);

-- Match Types
CREATE TABLE match_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Teams
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE RESTRICT,
    division_id INTEGER NOT NULL REFERENCES divisions(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_team_age_division UNIQUE (name, age_group_id, division_id)
);

-- Matches
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
    
    CONSTRAINT matches_home_away_different CHECK (home_team_id != away_team_id),
    CONSTRAINT matches_scores_non_negative CHECK (
        (home_score IS NULL OR home_score >= 0) AND
        (away_score IS NULL OR away_score >= 0)
    ),
    CONSTRAINT unique_manual_match UNIQUE NULLS NOT DISTINCT (
        home_team_id, away_team_id, match_date, season_id,
        age_group_id, match_type_id, division_id, match_id
    )
);

-- ============================================================================
-- RELATIONSHIP TABLES
-- ============================================================================

-- Team Mappings (for external name resolution)
CREATE TABLE team_mappings (
    id SERIAL PRIMARY KEY,
    external_name VARCHAR(255) NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_external_name_source UNIQUE (external_name, source)
);

-- Team Match Types
CREATE TABLE team_match_types (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_type_id INTEGER NOT NULL REFERENCES match_types(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_team_match_type UNIQUE (team_id, match_type_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_leagues_name ON leagues(name);
CREATE INDEX idx_divisions_league_id ON divisions(league_id);
CREATE INDEX idx_teams_age_group ON teams(age_group_id);
CREATE INDEX idx_teams_division ON teams(division_id);
CREATE INDEX idx_matches_home_team ON matches(home_team_id);
CREATE INDEX idx_matches_away_team ON matches(away_team_id);
CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_age_group ON matches(age_group_id);
CREATE INDEX idx_matches_division ON matches(division_id);
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_match_id ON matches(match_id);
CREATE INDEX idx_team_mappings_external ON team_mappings(external_name);
CREATE INDEX idx_team_mappings_team ON team_mappings(team_id);

-- ============================================================================
-- QUICK REFERENCE FOR MATCH-SCRAPER
-- ============================================================================

/*
KEY CHANGES IN v1.1.0:
1. New 'leagues' table - top-level organization
2. divisions.league_id column added (REQUIRED)
3. Division names unique within league (not globally)
4. Default "Homegrown" league created

IMPORTANT FOR MATCH-SCRAPER:
- When creating matches, continue using division_id
- League association is automatic through divisions.league_id
- No code changes needed if you're not creating divisions
- If creating divisions, must specify league_id

BACKWARD COMPATIBILITY:
✅ Existing match creation code works unchanged
✅ Teams/matches automatically linked to leagues via divisions
❌ Cannot create divisions without league_id
❌ Division names no longer globally unique

EXAMPLE MATCH CREATION (unchanged):
INSERT INTO matches (
    home_team_id, away_team_id, match_date,
    season_id, age_group_id, match_type_id, division_id,
    match_id, source, status
) VALUES (
    123, 456, '2025-10-30',
    1, 2, 1, 3,
    'external_12345', 'match-scraper', 'scheduled'
);
*/
