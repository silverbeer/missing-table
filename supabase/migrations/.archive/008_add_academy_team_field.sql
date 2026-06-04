-- Add academy_team boolean field to teams table
-- This field indicates if a team is an academy team or not

-- Add the academy_team column with default value false
ALTER TABLE teams 
ADD COLUMN academy_team BOOLEAN DEFAULT false;

-- Update all existing teams to have academy_team = false (explicit for clarity)
UPDATE teams 
SET academy_team = false 
WHERE academy_team IS NULL;

-- Add index for performance if needed for filtering academy teams
CREATE INDEX idx_teams_academy_team ON teams(academy_team);

-- Add comment for documentation
COMMENT ON COLUMN teams.academy_team IS 'Indicates if this team is an academy team (true) or regular team (false)';