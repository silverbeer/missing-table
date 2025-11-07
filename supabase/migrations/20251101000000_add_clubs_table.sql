-- ============================================================================
-- ADD CLUBS TABLE AND MIGRATE FROM PARENT_CLUB_ID
-- ============================================================================
-- Purpose: Create proper clubs table and migrate from parent_club_id architecture
-- Impact: Creates clubs table, migrates data, updates teams table structure
-- Author: Claude Code
-- Date: 2025-11-01
--
-- Why this change:
-- - Previous approach used self-referencing parent_club_id in teams table
-- - This conflated clubs (organizations) with teams (competition entities)
-- - New approach: clubs are separate entities, teams belong to a club AND a league
--
-- Example Structure (BEFORE):
--   teams:
--     IFA (parent_club_id: NULL) -- Parent club record
--     IFA Academy (parent_club_id: points to IFA)
--     IFA Homegrown (parent_club_id: points to IFA)
--
-- Example Structure (AFTER):
--   clubs:
--     IFA (id: 1, city: Weymouth, MA)
--
--   teams:
--     IFA Academy (club_id: 1, league_id: 1)
--     IFA Homegrown (club_id: 1, league_id: 2)
--     IFA Select (club_id: 1, league_id: 3)
--
-- Benefits:
-- - Clubs and teams are properly separated
-- - Teams can belong to both a club AND a league
-- - No need for team_aliases workaround
-- - Cleaner data model
-- ============================================================================

-- ============================================================================
-- STEP 1: CREATE CLUBS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    website VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Ensure club names are unique (case-insensitive)
    CONSTRAINT clubs_name_unique UNIQUE (name)
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_clubs_name ON clubs(name);
CREATE INDEX IF NOT EXISTS idx_clubs_is_active ON clubs(is_active);

-- Add comment
COMMENT ON TABLE clubs IS 'Organizations that field teams in one or more leagues (e.g., IFA, New England Revolution)';

-- Add trigger for updated_at
CREATE TRIGGER update_clubs_updated_at
    BEFORE UPDATE ON clubs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- STEP 2: MIGRATE EXISTING PARENT CLUBS TO CLUBS TABLE
-- ============================================================================

-- Insert parent clubs (teams that are referenced by parent_club_id) into clubs table
INSERT INTO clubs (name, city, created_at)
SELECT DISTINCT
    t.name,
    t.city,
    t.created_at
FROM teams t
WHERE EXISTS (
    SELECT 1 FROM teams child WHERE child.parent_club_id = t.id
)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- STEP 3: ADD CLUB_ID AND LEAGUE_ID TO TEAMS TABLE
-- ============================================================================

-- Add club_id column (nullable initially for migration)
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id) ON DELETE RESTRICT;

-- Add league_id column (nullable initially for migration)
-- Teams now belong to a league AND a club
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS league_id INTEGER REFERENCES leagues(id) ON DELETE RESTRICT;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_teams_club_id ON teams(club_id);
CREATE INDEX IF NOT EXISTS idx_teams_league_id ON teams(league_id);
CREATE INDEX IF NOT EXISTS idx_teams_club_league ON teams(club_id, league_id);

-- Add comments
COMMENT ON COLUMN teams.club_id IS 'The club/organization this team belongs to (e.g., IFA). NULL for independent teams.';
COMMENT ON COLUMN teams.league_id IS 'The league this team competes in (e.g., Homegrown, Academy, Elite)';

-- ============================================================================
-- STEP 4: MIGRATE DATA FROM PARENT_CLUB_ID TO CLUB_ID
-- ============================================================================

-- For teams that have a parent_club_id, set club_id to the corresponding club
UPDATE teams t
SET club_id = (
    SELECT c.id
    FROM clubs c
    JOIN teams parent ON parent.name = c.name
    WHERE parent.id = t.parent_club_id
)
WHERE t.parent_club_id IS NOT NULL;

-- ============================================================================
-- STEP 4.5: DELETE OLD PARENT CLUB TEAM RECORDS
-- ============================================================================

-- Delete teams that were parent clubs (they're now in the clubs table)
-- These are teams that had children (were referenced by other teams' parent_club_id)
DELETE FROM teams
WHERE id IN (
    SELECT DISTINCT parent.id
    FROM teams parent
    WHERE EXISTS (
        SELECT 1 FROM teams child WHERE child.parent_club_id = parent.id
    )
);

-- ============================================================================
-- STEP 5: SET DEFAULT LEAGUE FOR EXISTING TEAMS
-- ============================================================================

-- Assign all existing teams to "Homegrown" league as default
-- (can be updated later via admin interface)
UPDATE teams
SET league_id = (SELECT id FROM leagues WHERE name = 'Homegrown' LIMIT 1)
WHERE league_id IS NULL;

-- Make league_id required after migration
ALTER TABLE teams
ALTER COLUMN league_id SET NOT NULL;

-- ============================================================================
-- STEP 6: DROP PARENT_CLUB_ID COLUMN AND OLD FUNCTIONS
-- ============================================================================

-- Drop old helper functions that used parent_club_id
DROP FUNCTION IF EXISTS get_club_teams(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS is_parent_club(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS get_parent_club(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS check_parent_club_hierarchy() CASCADE;

-- Drop old trigger
DROP TRIGGER IF EXISTS validate_parent_club_hierarchy ON teams;

-- Drop old view
DROP VIEW IF EXISTS teams_with_parent;

-- Drop old constraints
ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_parent_not_self;

-- Drop old indexes
DROP INDEX IF EXISTS idx_teams_parent_club_id;
DROP INDEX IF EXISTS idx_teams_parent_club_age_group;

-- Finally, drop the parent_club_id column
ALTER TABLE teams DROP COLUMN IF EXISTS parent_club_id;

-- ============================================================================
-- STEP 7: CREATE NEW HELPER FUNCTIONS
-- ============================================================================

-- Function to get all teams for a club
CREATE OR REPLACE FUNCTION get_club_teams(p_club_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    club_id INTEGER,
    league_id INTEGER,
    league_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.name,
        t.club_id,
        t.league_id,
        l.name AS league_name,
        t.created_at
    FROM teams t
    JOIN leagues l ON t.league_id = l.id
    WHERE t.club_id = p_club_id
    ORDER BY l.name, t.name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION get_club_teams IS
'Returns all teams for a club across all leagues';

-- Function to get teams for a club in a specific league
CREATE OR REPLACE FUNCTION get_club_league_teams(p_club_id INTEGER, p_league_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    club_id INTEGER,
    league_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.name,
        t.club_id,
        t.league_id,
        t.created_at
    FROM teams t
    WHERE t.club_id = p_club_id
      AND t.league_id = p_league_id
    ORDER BY t.name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION get_club_league_teams IS
'Returns teams for a club in a specific league';

-- ============================================================================
-- STEP 8: CREATE VIEWS
-- ============================================================================

-- View: Teams with club and league information
CREATE OR REPLACE VIEW teams_with_details AS
SELECT
    t.id,
    t.name AS team_name,
    t.city,
    t.academy_team,
    c.id AS club_id,
    c.name AS club_name,
    c.city AS club_city,
    l.id AS league_id,
    l.name AS league_name,
    l.description AS league_description,
    t.created_at,
    t.updated_at
FROM teams t
LEFT JOIN clubs c ON t.club_id = c.id
JOIN leagues l ON t.league_id = l.id;

COMMENT ON VIEW teams_with_details IS
'Convenient view showing teams with their club and league information';

-- Grant access to views
GRANT SELECT ON teams_with_details TO authenticated;
GRANT SELECT ON teams_with_details TO anon;

-- ============================================================================
-- STEP 9: ADD UNIQUE CONSTRAINTS
-- ============================================================================

-- Ensure team names are unique within a club+league combination
-- This allows "IFA Academy" to exist in multiple leagues under the same club
ALTER TABLE teams
ADD CONSTRAINT teams_name_club_league_unique
UNIQUE (name, club_id, league_id);

-- ============================================================================
-- STEP 10: ENABLE RLS FOR CLUBS
-- ============================================================================

ALTER TABLE clubs ENABLE ROW LEVEL SECURITY;

-- Everyone can view clubs
DROP POLICY IF EXISTS clubs_select_all ON clubs;
CREATE POLICY clubs_select_all ON clubs FOR SELECT USING (true);

-- Only admins can modify clubs
DROP POLICY IF EXISTS clubs_admin_all ON clubs;
CREATE POLICY clubs_admin_all ON clubs FOR ALL USING (is_admin());

-- ============================================================================
-- STEP 11: GRANT PERMISSIONS FOR HELPER FUNCTIONS
-- ============================================================================

GRANT EXECUTE ON FUNCTION get_club_teams TO authenticated;
GRANT EXECUTE ON FUNCTION get_club_teams TO anon;
GRANT EXECUTE ON FUNCTION get_club_league_teams TO authenticated;
GRANT EXECUTE ON FUNCTION get_club_league_teams TO anon;

-- ============================================================================
-- MIGRATION GUIDE (COMMENTED)
-- ============================================================================

/*
MIGRATION GUIDE
===============

This migration automatically handles data migration from the old parent_club_id
structure to the new clubs table structure.

WHAT HAPPENS DURING MIGRATION:
------------------------------

1. Creates clubs table
2. Finds all teams that are "parent clubs" (have children via parent_club_id)
3. Creates club records for these parent teams
4. Updates child teams to reference the new club records
5. Sets all teams to "Homegrown" league by default
6. Removes parent_club_id column and related functions

AFTER MIGRATION:
---------------

1. Review clubs table:
   SELECT * FROM clubs ORDER BY name;

2. Review teams with new structure:
   SELECT * FROM teams_with_details ORDER BY club_name, league_name, team_name;

3. Update team league assignments if needed:
   UPDATE teams SET league_id = X WHERE name = 'Team Name';

ADDING NEW CLUBS:
----------------

1. Create club:
   INSERT INTO clubs (name, city, website)
   VALUES ('New Club', 'Boston, MA', 'https://newclub.com');

2. Create teams for the club:
   INSERT INTO teams (name, city, club_id, league_id)
   VALUES ('New Club Academy', 'Boston, MA',
           (SELECT id FROM clubs WHERE name = 'New Club'),
           (SELECT id FROM leagues WHERE name = 'Academy'));

QUERYING:
---------

-- Get all teams for a club
SELECT * FROM get_club_teams(1);

-- Get teams for a club in specific league
SELECT * FROM get_club_league_teams(1, 2);

-- Get all independent teams (no club)
SELECT * FROM teams WHERE club_id IS NULL;

-- Get all teams in a league
SELECT * FROM teams WHERE league_id = 1;
*/

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.3.0',
    '20251101000000_add_clubs_table',
    'Add clubs table and migrate from parent_club_id to club_id architecture'
);
