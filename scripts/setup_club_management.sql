-- Setup club-level management for team_manager role
-- This script:
-- 1. Adds club_id column to user_profiles
-- 2. Assigns tom_ifa to IFA Club for full club management

-- ============================================================
-- STEP 1: Add club_id column (from migration)
-- ============================================================

-- Add club_id column to user_profiles
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id) ON DELETE SET NULL;

-- Add index for club_id lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_club_id ON user_profiles(club_id);

-- Add constraint to ensure user has either team_id OR club_id, not both
ALTER TABLE user_profiles
DROP CONSTRAINT IF EXISTS chk_team_or_club_not_both;

ALTER TABLE user_profiles
ADD CONSTRAINT chk_team_or_club_not_both
CHECK (
    (team_id IS NULL AND club_id IS NULL) OR  -- No assignment
    (team_id IS NOT NULL AND club_id IS NULL) OR  -- Team-level manager
    (team_id IS NULL AND club_id IS NOT NULL)  -- Club-level manager
);

-- Add comment explaining the constraint
COMMENT ON COLUMN user_profiles.club_id IS 'Club ID for club-level managers. User can have either team_id (manages one team) OR club_id (manages all teams in club), but not both.';

-- ============================================================
-- STEP 2: Assign tom_ifa to IFA Club
-- ============================================================

-- Update tom_ifa to be a club manager for IFA Club (club_id = 1)
UPDATE user_profiles
SET club_id = 1,  -- IFA Club
    team_id = NULL,  -- Clear any team assignment
    updated_at = NOW()
WHERE username = 'tom_ifa';

-- Verify the assignment
SELECT
    username,
    display_name,
    role,
    team_id,
    club_id,
    CASE
        WHEN club_id IS NOT NULL THEN 'Club Manager'
        WHEN team_id IS NOT NULL THEN 'Team Manager'
        ELSE 'No Assignment'
    END as management_type
FROM user_profiles
WHERE username = 'tom_ifa';

-- Show all teams in IFA Club
SELECT
    t.id,
    t.name,
    t.city,
    c.name as club_name
FROM teams t
LEFT JOIN clubs c ON t.club_id = c.id
WHERE t.club_id = 1
ORDER BY t.name;

-- Update schema version
SELECT add_schema_version('1.5.0', 'setup_club_management', 'Add club-level management and assign tom_ifa to IFA Club');

-- ============================================================
-- SUCCESS MESSAGE
-- ============================================================
SELECT '✅ Club management setup complete!' as status,
       'tom_ifa is now managing IFA Club (all teams)' as message;
