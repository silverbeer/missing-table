-- Migration: Fix team_mappings unique constraint
--
-- Problem: The current constraint UNIQUE(team_id, age_group_id) prevents a team
--          from being in multiple divisions for the same age group.
--          Example: IFA U14 can't be in both MLS NEXT U14 AND Futsal U14.
--
-- Solution: Change to UNIQUE(team_id, age_group_id, division_id) so teams can
--           participate in multiple leagues/divisions per age group.

-- Step 1: Drop the old 2-column constraint
ALTER TABLE team_mappings
DROP CONSTRAINT IF EXISTS team_mappings_team_id_age_group_id_key;

-- Step 2: Add new 3-column constraint
-- This allows a team to be in different divisions for the same age group
ALTER TABLE team_mappings
ADD CONSTRAINT team_mappings_team_age_group_division_unique
UNIQUE (team_id, age_group_id, division_id);

-- Add helpful comment
COMMENT ON CONSTRAINT team_mappings_team_age_group_division_unique ON team_mappings
IS 'Teams can participate in multiple divisions per age group (e.g., MLS NEXT and Futsal)';
