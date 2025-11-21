-- Migration: Add club_fan role and consolidate fan management at club level
-- This migration replaces team-fan with club-fan for simpler fan management

-- First, ensure club_id column exists in invitations (may have been missed)
ALTER TABLE invitations
ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id);

COMMENT ON COLUMN invitations.club_id IS 'Club ID for club_manager and club_fan invites';

-- Update user_profiles role constraint to include club-fan
ALTER TABLE user_profiles
DROP CONSTRAINT IF EXISTS user_profiles_role_check;

ALTER TABLE user_profiles
ADD CONSTRAINT user_profiles_role_check
CHECK (role IN (
    'admin',
    'club_manager',
    'club-fan',
    'club_fan',
    'team-manager',
    'team_manager',
    'team-player',
    'team_player',
    'team-fan',
    'team_fan'
));

-- Update comment documenting the role hierarchy
COMMENT ON COLUMN user_profiles.role IS 'User role: admin > club_manager > team-manager > team-player > club-fan/team-fan. Club fans can view all teams in their assigned club.';

-- Update invitations invite_type constraint to include club_fan
-- First check what the current constraint looks like
DO $$
BEGIN
    -- Drop existing constraint if it exists
    ALTER TABLE invitations
    DROP CONSTRAINT IF EXISTS invitations_invite_type_check;
EXCEPTION
    WHEN undefined_object THEN
        NULL; -- Constraint doesn't exist, continue
END $$;

-- Add updated constraint with club_fan
ALTER TABLE invitations
ADD CONSTRAINT invitations_invite_type_check
CHECK (invite_type IN (
    'club_manager',
    'club_fan',
    'team_manager',
    'team_player',
    'team_fan'
));

-- Update schema version
SELECT add_schema_version('1.3.0', 'add_club_fan_role', 'Add club_fan role for club-level fan management, keep team_fan for backwards compatibility');
