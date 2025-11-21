-- ============================================================================
-- BASELINE SCHEMA MIGRATION
-- ============================================================================
-- Schema Version: 1.0.0
-- Created: 2025-10-28
-- Purpose: Consolidate all schema migrations into a single baseline
-- Source: Current dev database schema (most complete and actively used)
--
-- This migration creates the complete schema including:
-- ✓ Core tables (age_groups, seasons, teams, matches, etc.)
-- ✓ Auth system (user_profiles, invitations, team_manager_assignments)
-- ✓ Reference tables (divisions, match_types)
-- ✓ Relationship tables (team_mappings, team_match_types)
-- ✓ Enums (match_status)
-- ✓ Functions (is_admin, is_team_manager, manages_team, reset_all_sequences)
-- ✓ RLS policies for all tables
-- ✓ Indexes for performance
-- ✓ Constraints for data integrity
--
-- Previous migrations consolidated from supabase-local/ directory
-- ============================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ENUMS
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE match_status AS ENUM ('scheduled', 'completed', 'postponed', 'cancelled', 'tbd', 'live');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================

-- Schema Version Table
-- Tracks schema version history and current deployed version
CREATE TABLE IF NOT EXISTS schema_version (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL,
    migration_name VARCHAR(255) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(100) DEFAULT CURRENT_USER
);

-- Insert baseline version
INSERT INTO schema_version (version, migration_name, description)
VALUES ('1.0.0', '20251028000001_baseline_schema', 'Initial baseline schema consolidation')
ON CONFLICT DO NOTHING;

-- Function to get current schema version
CREATE OR REPLACE FUNCTION get_schema_version()
RETURNS TABLE(version VARCHAR, applied_at TIMESTAMP WITH TIME ZONE, description TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT sv.version, sv.applied_at, sv.description
    FROM schema_version sv
    ORDER BY sv.applied_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Function to add new schema version (for future migrations)
CREATE OR REPLACE FUNCTION add_schema_version(
    p_version VARCHAR,
    p_migration_name VARCHAR,
    p_description TEXT DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO schema_version (version, migration_name, description)
    VALUES (p_version, p_migration_name, p_description);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Age Groups
CREATE TABLE IF NOT EXISTS age_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seasons
CREATE TABLE IF NOT EXISTS seasons (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Match Types (formerly game_types)
CREATE TABLE IF NOT EXISTS match_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Divisions
CREATE TABLE IF NOT EXISTS divisions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    academy_team BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Team Mappings (links teams to age groups and divisions)
CREATE TABLE IF NOT EXISTS team_mappings (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE CASCADE,
    division_id INTEGER REFERENCES divisions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, age_group_id, division_id)
);

-- Team Match Types (which match types each team uses)
CREATE TABLE IF NOT EXISTS team_match_types (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_type_id INTEGER NOT NULL REFERENCES match_types(id) ON DELETE CASCADE,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, match_type_id, age_group_id)
);

-- Matches (formerly games)
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    match_date DATE NOT NULL,
    home_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    home_score INTEGER,
    away_score INTEGER,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE CASCADE,
    match_type_id INTEGER NOT NULL REFERENCES match_types(id) ON DELETE CASCADE,
    division_id INTEGER REFERENCES divisions(id) ON DELETE SET NULL,

    -- Scraper fields
    mls_match_id VARCHAR(100),
    data_source VARCHAR(50) DEFAULT 'manual',
    last_scraped_at TIMESTAMP WITH TIME ZONE,
    score_locked BOOLEAN DEFAULT false,
    match_id VARCHAR(255) UNIQUE,

    -- Status
    match_status match_status DEFAULT 'scheduled',

    -- Audit fields
    created_by UUID,
    updated_by UUID,
    source VARCHAR(50) DEFAULT 'manual',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (home_team_id != away_team_id),
    CONSTRAINT unique_manual_match UNIQUE (home_team_id, away_team_id, match_date, season_id, age_group_id, match_type_id, division_id)
);

-- ============================================================================
-- AUTH & USER MANAGEMENT TABLES
-- ============================================================================

-- User Profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY,
    role VARCHAR(50) NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'team-manager', 'team_manager', 'team-fan', 'team-player', 'user')),
    team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    display_name VARCHAR(200),
    username VARCHAR(100) UNIQUE,
    email VARCHAR(255) UNIQUE,
    phone_number VARCHAR(20),
    player_number VARCHAR(10),
    positions TEXT DEFAULT '[]',
    assigned_age_group_id INTEGER REFERENCES age_groups(id) ON DELETE SET NULL,
    invited_via_code VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Invitations
CREATE TABLE IF NOT EXISTS invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invite_code VARCHAR(12) NOT NULL UNIQUE,
    invited_by_user_id UUID,
    invite_type VARCHAR(50) NOT NULL,
    team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    age_group_id INTEGER REFERENCES age_groups(id) ON DELETE SET NULL,
    email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    expires_at TIMESTAMP WITH TIME ZONE,
    used_at TIMESTAMP WITH TIME ZONE,
    used_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Team Manager Assignments
CREATE TABLE IF NOT EXISTS team_manager_assignments (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, team_id)
);

-- Service Accounts
CREATE TABLE IF NOT EXISTS service_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL UNIQUE,
    permissions TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id);
CREATE INDEX IF NOT EXISTS idx_matches_age_group ON matches(age_group_id);
CREATE INDEX IF NOT EXISTS idx_matches_match_type ON matches(match_type_id);
CREATE INDEX IF NOT EXISTS idx_matches_division ON matches(division_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_mls_match_id ON matches(mls_match_id);
CREATE INDEX IF NOT EXISTS idx_matches_match_status ON matches(match_status);

CREATE INDEX IF NOT EXISTS idx_team_mappings_team ON team_mappings(team_id);
CREATE INDEX IF NOT EXISTS idx_team_mappings_age_group ON team_mappings(age_group_id);
CREATE INDEX IF NOT EXISTS idx_team_mappings_division ON team_mappings(division_id);

CREATE INDEX IF NOT EXISTS idx_team_manager_assignments_user ON team_manager_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_team_manager_assignments_team ON team_manager_assignments(team_id);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Helper function: Check if current user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM user_profiles
        WHERE id = auth.uid()
        AND role = 'admin'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Helper function: Check if current user is team manager
CREATE OR REPLACE FUNCTION is_team_manager()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM user_profiles
        WHERE id = auth.uid()
        AND role = 'team_manager'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Helper function: Check if current user manages specific team
CREATE OR REPLACE FUNCTION manages_team(team_id_param INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM team_manager_assignments
        WHERE user_id = auth.uid()
        AND team_id = team_id_param
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Note: reset_all_sequences() function is defined in migration 20251023000021

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on tables
ALTER TABLE age_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE divisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_match_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_manager_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_accounts ENABLE ROW LEVEL SECURITY;

-- Note: user_profiles RLS disabled for backend access
ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- RLS POLICIES: Reference Tables (read-only for all, write for admins)
-- ============================================================================

-- Age Groups Policies
DROP POLICY IF EXISTS age_groups_select_all ON age_groups;
CREATE POLICY age_groups_select_all ON age_groups FOR SELECT USING (true);
DROP POLICY IF EXISTS age_groups_admin_all ON age_groups;
CREATE POLICY age_groups_admin_all ON age_groups FOR ALL USING (is_admin());

-- Seasons Policies
DROP POLICY IF EXISTS seasons_select_all ON seasons;
CREATE POLICY seasons_select_all ON seasons FOR SELECT USING (true);
DROP POLICY IF EXISTS seasons_admin_all ON seasons;
CREATE POLICY seasons_admin_all ON seasons FOR ALL USING (is_admin());

-- Match Types Policies
DROP POLICY IF EXISTS match_types_select_all ON match_types;
CREATE POLICY match_types_select_all ON match_types FOR SELECT USING (true);
DROP POLICY IF EXISTS match_types_admin_all ON match_types;
CREATE POLICY match_types_admin_all ON match_types FOR ALL USING (is_admin());

-- Divisions Policies
DROP POLICY IF EXISTS divisions_select_all ON divisions;
CREATE POLICY divisions_select_all ON divisions FOR SELECT USING (true);
DROP POLICY IF EXISTS divisions_admin_all ON divisions;
CREATE POLICY divisions_admin_all ON divisions FOR ALL USING (is_admin());

-- ============================================================================
-- RLS POLICIES: Teams
-- ============================================================================

DROP POLICY IF EXISTS teams_select_all ON teams;
CREATE POLICY teams_select_all ON teams FOR SELECT USING (true);
DROP POLICY IF EXISTS teams_admin_all ON teams;
CREATE POLICY teams_admin_all ON teams FOR ALL USING (is_admin());

-- Team Mappings Policies
DROP POLICY IF EXISTS team_mappings_select_all ON team_mappings;
CREATE POLICY team_mappings_select_all ON team_mappings FOR SELECT USING (true);
DROP POLICY IF EXISTS team_mappings_admin_all ON team_mappings;
CREATE POLICY team_mappings_admin_all ON team_mappings FOR ALL USING (is_admin());

-- Team Match Types Policies
DROP POLICY IF EXISTS team_match_types_select_all ON team_match_types;
CREATE POLICY team_match_types_select_all ON team_match_types FOR SELECT USING (true);
DROP POLICY IF EXISTS team_match_types_admin_all ON team_match_types;
CREATE POLICY team_match_types_admin_all ON team_match_types FOR ALL USING (is_admin());

-- ============================================================================
-- RLS POLICIES: Matches
-- ============================================================================

-- Everyone can view matches
DROP POLICY IF EXISTS matches_select_all ON matches;
CREATE POLICY matches_select_all ON matches FOR SELECT USING (true);

-- Admins can do everything
DROP POLICY IF EXISTS matches_admin_all ON matches;
CREATE POLICY matches_admin_all ON matches FOR ALL USING (is_admin());

-- Team managers can insert matches for their teams
DROP POLICY IF EXISTS matches_manager_insert ON matches;
CREATE POLICY matches_manager_insert ON matches FOR INSERT WITH CHECK (
    is_team_manager() AND (
        manages_team(home_team_id) OR manages_team(away_team_id)
    )
);

-- Team managers can update matches for their teams
DROP POLICY IF EXISTS matches_manager_update ON matches;
CREATE POLICY matches_manager_update ON matches FOR UPDATE USING (
    is_team_manager() AND (
        manages_team(home_team_id) OR manages_team(away_team_id)
    )
);

-- Team managers can delete matches for their teams
DROP POLICY IF EXISTS matches_manager_delete ON matches;
CREATE POLICY matches_manager_delete ON matches FOR DELETE USING (
    is_team_manager() AND (
        manages_team(home_team_id) OR manages_team(away_team_id)
    )
);

-- ============================================================================
-- RLS POLICIES: Invitations
-- ============================================================================

DROP POLICY IF EXISTS invitations_admin_all ON invitations;
CREATE POLICY invitations_admin_all ON invitations FOR ALL USING (is_admin());
DROP POLICY IF EXISTS invitations_select_own ON invitations;
CREATE POLICY invitations_select_own ON invitations FOR SELECT USING (auth.uid() = used_by_user_id);

-- ============================================================================
-- RLS POLICIES: Team Manager Assignments
-- ============================================================================

DROP POLICY IF EXISTS team_manager_assignments_select_authenticated ON team_manager_assignments;
CREATE POLICY team_manager_assignments_select_authenticated ON team_manager_assignments
    FOR SELECT USING (auth.role() = 'authenticated');
DROP POLICY IF EXISTS team_manager_assignments_admin_all ON team_manager_assignments;
CREATE POLICY team_manager_assignments_admin_all ON team_manager_assignments
    FOR ALL USING (is_admin());

-- ============================================================================
-- RLS POLICIES: Service Accounts
-- ============================================================================

DROP POLICY IF EXISTS service_accounts_admin_all ON service_accounts;
CREATE POLICY service_accounts_admin_all ON service_accounts FOR ALL USING (is_admin());

-- ============================================================================
-- BASELINE SCHEMA COMPLETE
-- ============================================================================
