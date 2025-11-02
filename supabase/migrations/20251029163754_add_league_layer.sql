-- ============================================================================
-- ADD LEAGUE LAYER
-- ============================================================================
-- Purpose: Add League organizational layer above Divisions
-- Impact: Creates leagues table, adds league_id to divisions, migrates data
-- Author: Claude Code
-- Date: 2025-10-29

-- ============================================================================
-- CREATE LEAGUES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS leagues (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create default "Homegrown" league
INSERT INTO leagues (name, description, is_active)
VALUES ('Homegrown', 'Default league for all existing divisions and teams', true);

-- ============================================================================
-- ADD LEAGUE_ID TO DIVISIONS
-- ============================================================================

-- Add league_id column (nullable initially for data migration)
ALTER TABLE divisions
ADD COLUMN IF NOT EXISTS league_id INTEGER REFERENCES leagues(id) ON DELETE RESTRICT;

-- Migrate all existing divisions to "Homegrown" league
UPDATE divisions
SET league_id = (SELECT id FROM leagues WHERE name = 'Homegrown')
WHERE league_id IS NULL;

-- Make league_id required after migration
ALTER TABLE divisions
ALTER COLUMN league_id SET NOT NULL;

-- ============================================================================
-- UPDATE UNIQUE CONSTRAINTS
-- ============================================================================

-- Drop old global unique constraint on division name
ALTER TABLE divisions DROP CONSTRAINT IF EXISTS divisions_name_key;

-- Add new unique constraint: division name unique within league
ALTER TABLE divisions
ADD CONSTRAINT divisions_name_league_id_key UNIQUE (name, league_id);

-- ============================================================================
-- ADD INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_divisions_league_id ON divisions(league_id);
CREATE INDEX IF NOT EXISTS idx_leagues_name ON leagues(name);

-- ============================================================================
-- ADD UPDATED_AT TRIGGER FOR LEAGUES
-- ============================================================================

-- Reuse existing update_updated_at_column function
CREATE TRIGGER update_leagues_updated_at
    BEFORE UPDATE ON leagues
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ENABLE RLS
-- ============================================================================

ALTER TABLE leagues ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- RLS POLICIES FOR LEAGUES
-- ============================================================================

-- Everyone can view leagues
DROP POLICY IF EXISTS leagues_select_all ON leagues;
CREATE POLICY leagues_select_all ON leagues FOR SELECT USING (true);

-- Only admins can modify leagues
DROP POLICY IF EXISTS leagues_admin_all ON leagues;
CREATE POLICY leagues_admin_all ON leagues FOR ALL USING (is_admin());

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.1.0',
    '20251029163754_add_league_layer',
    'Add league organizational layer above divisions'
);
