-- Add club_id to user_profiles for club-level team management
-- This allows team_manager role to manage either:
--   1. A single team (team_id set, club_id NULL)
--   2. All teams in a club (club_id set, team_id NULL)
--   3. No assignment (both NULL)

-- Add club_id column to user_profiles
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id) ON DELETE SET NULL;

-- Add index for club_id lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_club_id ON user_profiles(club_id);

-- Add constraint to ensure user has either team_id OR club_id, not both
ALTER TABLE user_profiles
ADD CONSTRAINT chk_team_or_club_not_both
CHECK (
    (team_id IS NULL AND club_id IS NULL) OR  -- No assignment
    (team_id IS NOT NULL AND club_id IS NULL) OR  -- Team-level manager
    (team_id IS NULL AND club_id IS NOT NULL)  -- Club-level manager
);

-- Add comment explaining the constraint
COMMENT ON COLUMN user_profiles.club_id IS 'Club ID for club-level managers. User can have either team_id (manages one team) OR club_id (manages all teams in club), but not both.';

-- Update schema version
SELECT add_schema_version('1.5.0', 'add_club_id_to_user_profiles', 'Add club-level management support for team managers');
