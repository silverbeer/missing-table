-- Rename team_age_groups table to team_mappings
-- This table now contains age group and division mappings for teams

-- Rename the table
ALTER TABLE team_age_groups RENAME TO team_mappings;

-- The indexes will automatically be renamed with the table, but let's rename them explicitly for clarity
ALTER INDEX idx_team_age_groups_team RENAME TO idx_team_mappings_team;
ALTER INDEX idx_team_age_groups_age_group RENAME TO idx_team_mappings_age_group;
ALTER INDEX idx_team_age_groups_division RENAME TO idx_team_mappings_division;

-- The foreign key constraints are automatically updated with the table rename
-- No need to update them explicitly

-- Add a comment to document the table's purpose
COMMENT ON TABLE team_mappings IS 'Maps teams to their age groups and divisions';
COMMENT ON COLUMN team_mappings.team_id IS 'Reference to the team';
COMMENT ON COLUMN team_mappings.age_group_id IS 'Reference to the age group';
COMMENT ON COLUMN team_mappings.division_id IS 'Reference to the division (optional)';