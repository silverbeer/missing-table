-- Add player number and positions to user_profiles table
-- Migration: 009_add_player_fields.sql

-- Add player_number column (unique per team)
ALTER TABLE user_profiles 
ADD COLUMN player_number INTEGER;

-- Add positions column as JSON array
ALTER TABLE user_profiles 
ADD COLUMN positions JSONB DEFAULT '[]'::jsonb;

-- Create partial unique index for player_number per team (allows NULL values)
CREATE UNIQUE INDEX idx_player_number_per_team 
ON user_profiles (team_id, player_number) 
WHERE player_number IS NOT NULL;

-- Add constraint to ensure player_number is positive
ALTER TABLE user_profiles 
ADD CONSTRAINT chk_player_number_positive 
CHECK (player_number IS NULL OR player_number > 0);

-- Add comment explaining the positions format
COMMENT ON COLUMN user_profiles.positions IS 'Array of position abbreviations (e.g., ["ST", "CF", "LW"])';
COMMENT ON COLUMN user_profiles.player_number IS 'Jersey number unique per team';