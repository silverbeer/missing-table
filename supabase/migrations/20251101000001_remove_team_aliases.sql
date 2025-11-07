-- ============================================================================
-- REMOVE TEAM_ALIASES TABLE
-- ============================================================================
-- Purpose: Remove team_aliases workaround - no longer needed with clubs architecture
-- Impact: Drops team_aliases table and related objects
-- Author: Claude Code
-- Date: 2025-11-01
--
-- Why this change:
-- - team_aliases was a workaround to map external team names to internal teams by league
-- - With the new clubs architecture, teams are naturally scoped by club+league
-- - Each team is a distinct entity per league, so no aliases needed
-- - External scrapers can match directly on team name + league combination
--
-- Example (OLD with aliases):
--   teams: "IFA" (generic)
--   team_aliases: "IFA" → team_id=1, league_id=1
--   team_aliases: "IFA" → team_id=2, league_id=2
--
-- Example (NEW with clubs):
--   clubs: "IFA"
--   teams: "IFA Academy" (club_id=1, league_id=1)
--   teams: "IFA Homegrown" (club_id=1, league_id=2)
--   teams: "IFA Select" (club_id=1, league_id=3)
-- ============================================================================

-- ============================================================================
-- DROP TEAM_ALIASES TABLE
-- ============================================================================

-- Drop RLS policies first
DROP POLICY IF EXISTS "Team aliases are viewable by everyone" ON team_aliases;
DROP POLICY IF EXISTS "Only admins can insert team aliases" ON team_aliases;
DROP POLICY IF EXISTS "Only admins can update team aliases" ON team_aliases;
DROP POLICY IF EXISTS "Only admins can delete team aliases" ON team_aliases;

-- Drop triggers
DROP TRIGGER IF EXISTS update_team_aliases_updated_at ON team_aliases;

-- Drop indexes
DROP INDEX IF EXISTS idx_team_aliases_lookup;
DROP INDEX IF EXISTS idx_team_aliases_team;

-- Drop the table
DROP TABLE IF EXISTS team_aliases CASCADE;

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

/*
MIGRATION NOTES
===============

The team_aliases table has been removed because it's no longer needed.

OLD APPROACH (team_aliases):
- Single team entity with multiple aliases per league
- Complex mapping logic
- Requires manual alias management

NEW APPROACH (clubs + teams):
- Teams are distinct entities per club+league combination
- Direct matching on team name + league
- Simpler data model

IMPACT ON MATCH SCRAPING:
------------------------

If you have external scrapers (e.g., match-scraper), update them to:

1. Match teams using: team.name + team.league_id
2. Query: SELECT * FROM teams WHERE name = 'Team Name' AND league_id = X

EXAMPLE QUERIES:
---------------

-- Find team by name and league (for match scraping)
SELECT * FROM teams
WHERE name = 'IFA Academy'
  AND league_id = (SELECT id FROM leagues WHERE name = 'Homegrown');

-- Get all teams for external source matching
SELECT
    t.id,
    t.name,
    c.name AS club_name,
    l.name AS league_name
FROM teams t
LEFT JOIN clubs c ON t.club_id = c.id
JOIN leagues l ON t.league_id = l.id
ORDER BY c.name, l.name, t.name;
*/

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.3.1',
    '20251101000001_remove_team_aliases',
    'Remove team_aliases table - no longer needed with clubs architecture'
);
