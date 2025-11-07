-- Migration: Fix teams uniqueness constraint
--
-- Problem: The old teams_name_academy_unique constraint used the academy_team boolean
--          to distinguish between teams in different leagues. This was confusing because
--          academy_team should only indicate Pro Academy status, not league membership.
--
-- Solution: Add division_id to teams table and use UNIQUE(name, division_id) instead.
--          This properly reflects that a team name is unique within a division, and
--          divisions already capture the league relationship.

-- Step 1: Add division_id column (nullable initially for existing data)
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS division_id INTEGER;

-- Step 2: Populate division_id from team_mappings
-- Each team should have a single division (as per application model)
-- Get the division_id from the first team_mapping entry for each team
UPDATE teams t
SET division_id = (
    SELECT tm.division_id
    FROM team_mappings tm
    WHERE tm.team_id = t.id
    LIMIT 1
)
WHERE t.division_id IS NULL;

-- Step 3: Make division_id NOT NULL and add foreign key
ALTER TABLE teams
ALTER COLUMN division_id SET NOT NULL;

ALTER TABLE teams
ADD CONSTRAINT teams_division_id_fkey
FOREIGN KEY (division_id) REFERENCES divisions(id) ON DELETE RESTRICT;

-- Step 4: Drop the old constraint that uses academy_team
-- This constraint was: UNIQUE(name, academy_team)
-- It may or may not exist depending on when the database was created
DROP INDEX IF EXISTS teams_name_academy_unique;
ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_name_academy_unique;

-- Step 5: Add new constraint: UNIQUE(name, division_id)
-- This properly ensures team names are unique within a division
ALTER TABLE teams
ADD CONSTRAINT teams_name_division_unique
UNIQUE (name, division_id);

-- Step 6: Create index for performance on common queries
CREATE INDEX IF NOT EXISTS idx_teams_division_id ON teams(division_id);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- Add helpful comment
COMMENT ON COLUMN teams.division_id IS 'The division this team competes in. All age groups for this team use this division.';
COMMENT ON CONSTRAINT teams_name_division_unique ON teams IS 'Team names must be unique within a division. Teams in different divisions can have the same name.';
