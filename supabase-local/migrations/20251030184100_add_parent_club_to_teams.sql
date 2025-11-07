-- ============================================================================
-- ADD PARENT CLUB SUPPORT TO TEAMS
-- ============================================================================
-- Purpose: Enable clubs to have multiple teams across different leagues
-- Impact: Adds parent_club_id to teams table for club hierarchy
-- Author: Claude Code
-- Date: 2025-10-30
--
-- Use Case:
-- - Clubs like "IFA" can have both "IFA Academy" and "IFA Homegrown" teams
-- - Each team is a distinct entity (different players, coaches, rosters)
-- - Parent club links related teams together
-- - Supports multi-league organizations
--
-- Example Structure:
--   IFA (parent_club_id: NULL) -- Parent club record
--     └── IFA Academy (parent_club_id: points to IFA)
--     └── IFA Homegrown (parent_club_id: points to IFA)
--
-- ============================================================================

-- ============================================================================
-- ADD PARENT_CLUB_ID COLUMN
-- ============================================================================

-- Add parent_club_id column (nullable, self-referencing)
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS parent_club_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;

-- Add helpful comment
COMMENT ON COLUMN teams.parent_club_id IS
'References parent club for multi-league organizations. NULL for standalone teams or parent club records. Used to group teams like "IFA Academy" and "IFA Homegrown" under parent "IFA".';

-- ============================================================================
-- ADD INDEXES
-- ============================================================================

-- Index for querying all teams under a parent club
CREATE INDEX IF NOT EXISTS idx_teams_parent_club_id ON teams(parent_club_id);

-- Composite index for parent club + age group queries
-- Useful for: "All IFA teams in U14 age group"
CREATE INDEX IF NOT EXISTS idx_teams_parent_club_age_group ON teams(parent_club_id, id)
WHERE parent_club_id IS NOT NULL;

-- ============================================================================
-- ADD HELPER FUNCTIONS
-- ============================================================================

-- Function to get all teams for a club (parent + children)
CREATE OR REPLACE FUNCTION get_club_teams(p_club_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    city VARCHAR(100),
    academy_team BOOLEAN,
    parent_club_id INTEGER,
    is_parent BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.name,
        t.city,
        t.academy_team,
        t.parent_club_id,
        (t.id = p_club_id) AS is_parent,
        t.created_at
    FROM teams t
    WHERE t.id = p_club_id OR t.parent_club_id = p_club_id
    ORDER BY
        CASE WHEN t.id = p_club_id THEN 0 ELSE 1 END,  -- Parent first
        t.name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION get_club_teams IS
'Returns all teams for a club (parent club + all child teams). Pass the parent club ID.';

-- Function to check if a team is a parent club
CREATE OR REPLACE FUNCTION is_parent_club(p_team_id INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM teams WHERE parent_club_id = p_team_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION is_parent_club IS
'Returns true if the team is a parent club (has child teams).';

-- Function to get parent club for a team
CREATE OR REPLACE FUNCTION get_parent_club(p_team_id INTEGER)
RETURNS TABLE(
    id INTEGER,
    name VARCHAR(200),
    city VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.name,
        p.city
    FROM teams t
    JOIN teams p ON t.parent_club_id = p.id
    WHERE t.id = p_team_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

COMMENT ON FUNCTION get_parent_club IS
'Returns parent club information for a team (if exists).';

-- ============================================================================
-- DATA VALIDATION CONSTRAINTS
-- ============================================================================

-- Add constraint: parent_club_id cannot reference itself
ALTER TABLE teams
ADD CONSTRAINT teams_parent_not_self CHECK (id != parent_club_id);

-- Add constraint: prevent circular references (max 1 level deep)
-- A child team cannot be a parent itself
CREATE OR REPLACE FUNCTION check_parent_club_hierarchy()
RETURNS TRIGGER AS $$
BEGIN
    -- If this team has a parent, it cannot be a parent itself
    IF NEW.parent_club_id IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM teams WHERE parent_club_id = NEW.id) THEN
            RAISE EXCEPTION 'Team with ID % already has child teams and cannot have a parent club. Only one level of hierarchy is allowed.', NEW.id;
        END IF;
    END IF;

    -- If setting a parent, verify the parent doesn't have a parent (one level only)
    IF NEW.parent_club_id IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM teams WHERE id = NEW.parent_club_id AND parent_club_id IS NOT NULL) THEN
            RAISE EXCEPTION 'Parent club (ID %) cannot itself be a child team. Only one level of hierarchy is allowed.', NEW.parent_club_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_parent_club_hierarchy
    BEFORE INSERT OR UPDATE OF parent_club_id ON teams
    FOR EACH ROW
    EXECUTE FUNCTION check_parent_club_hierarchy();

COMMENT ON TRIGGER validate_parent_club_hierarchy ON teams IS
'Prevents circular references and enforces single-level parent-child hierarchy.';

-- ============================================================================
-- ADD VIEWS FOR CONVENIENCE
-- ============================================================================

-- View: Teams with parent club information
CREATE OR REPLACE VIEW teams_with_parent AS
SELECT
    t.id,
    t.name,
    t.city,
    t.academy_team,
    t.parent_club_id,
    p.name AS parent_club_name,
    p.city AS parent_club_city,
    (t.parent_club_id IS NULL) AS is_standalone,
    (EXISTS (SELECT 1 FROM teams c WHERE c.parent_club_id = t.id)) AS is_parent_club,
    t.created_at,
    t.updated_at
FROM teams t
LEFT JOIN teams p ON t.parent_club_id = p.id;

COMMENT ON VIEW teams_with_parent IS
'Convenient view showing teams with their parent club information.';

-- Grant access to view
GRANT SELECT ON teams_with_parent TO authenticated;
GRANT SELECT ON teams_with_parent TO anon;

-- ============================================================================
-- ENABLE RLS ON HELPER FUNCTIONS
-- ============================================================================

-- Grant execute permissions for helper functions
GRANT EXECUTE ON FUNCTION get_club_teams TO authenticated;
GRANT EXECUTE ON FUNCTION get_club_teams TO anon;
GRANT EXECUTE ON FUNCTION is_parent_club TO authenticated;
GRANT EXECUTE ON FUNCTION is_parent_club TO anon;
GRANT EXECUTE ON FUNCTION get_parent_club TO authenticated;
GRANT EXECUTE ON FUNCTION get_parent_club TO anon;

-- ============================================================================
-- MIGRATION GUIDE (COMMENTED)
-- ============================================================================

/*
MIGRATION GUIDE FOR EXISTING DATA
==================================

This migration adds the parent_club_id column but does NOT automatically
create parent clubs or modify existing team names. This allows you to
migrate data gradually.

RECOMMENDED MIGRATION STEPS:
----------------------------

1. For clubs with teams in multiple leagues (e.g., IFA):

   a) Create parent club record:
      INSERT INTO teams (name, city)
      VALUES ('IFA', 'Weymouth, MA');
      -- Returns id (e.g., 100)

   b) Update child teams:
      UPDATE teams SET parent_club_id = 100
      WHERE id IN (101, 102);  -- IFA Academy, IFA Homegrown

   c) Rename teams for clarity (optional):
      UPDATE teams SET name = 'IFA Academy' WHERE id = 101;
      UPDATE teams SET name = 'IFA Homegrown' WHERE id = 102;

2. For standalone teams (no multi-league presence):
   - No action needed
   - parent_club_id remains NULL

3. Verify hierarchy:
   SELECT * FROM teams_with_parent;
   SELECT * FROM get_club_teams(100);  -- Replace 100 with parent club ID

NAMING CONVENTIONS:
------------------
- Parent Club: "IFA", "New England Revolution"
- Child Teams: "IFA Academy", "IFA Homegrown", "IFA Development"
- Format: "{Club Name} {League Context}"

QUERYING EXAMPLES:
-----------------

-- Get all teams for a club
SELECT * FROM get_club_teams(100);

-- Get all parent clubs
SELECT * FROM teams WHERE parent_club_id IS NULL AND
  EXISTS (SELECT 1 FROM teams c WHERE c.parent_club_id = teams.id);

-- Get all standalone teams
SELECT * FROM teams WHERE parent_club_id IS NULL AND
  NOT EXISTS (SELECT 1 FROM teams c WHERE c.parent_club_id = teams.id);

-- Get all child teams
SELECT * FROM teams WHERE parent_club_id IS NOT NULL;

-- Get parent club for a team
SELECT * FROM get_parent_club(101);
*/

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.2.0',
    '20251030184100_add_parent_club_to_teams',
    'Add parent_club_id to teams for multi-league club support'
);
