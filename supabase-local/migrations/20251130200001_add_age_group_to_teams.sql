-- Add age_group_id to teams table
-- Each team belongs to a specific age group (e.g., U14, U15, U16)

-- Add the column
ALTER TABLE teams
ADD COLUMN IF NOT EXISTS age_group_id INTEGER REFERENCES age_groups(id);

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_teams_age_group_id ON teams(age_group_id);

-- Add comment explaining the relationship
COMMENT ON COLUMN teams.age_group_id IS 'The age group this team competes in (e.g., U14, U15). Each team in youth soccer is age-group specific.';
