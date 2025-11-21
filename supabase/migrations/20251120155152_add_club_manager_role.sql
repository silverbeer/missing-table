-- Migration: Add club_manager role and remove unused user role
-- This migration updates the role system to support club-level management

-- Drop the existing role check constraint
ALTER TABLE user_profiles
DROP CONSTRAINT IF EXISTS user_profiles_role_check;

-- Add new constraint with club_manager role and without user role
-- Keeping both hyphenated and underscored versions for backwards compatibility
ALTER TABLE user_profiles
ADD CONSTRAINT user_profiles_role_check
CHECK (role IN (
    'admin',
    'club_manager',
    'team-manager',
    'team_manager',
    'team-player',
    'team_player',
    'team-fan',
    'team_fan'
));

-- Add comment documenting the role hierarchy
COMMENT ON COLUMN user_profiles.role IS 'User role: admin > club_manager > team-manager > team-player/team-fan. Club managers can manage all teams in their assigned club.';

-- Add club_id column to invitations table for club_manager invites
ALTER TABLE invitations
ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id);

-- Add comment for club_id
COMMENT ON COLUMN invitations.club_id IS 'Club ID for club_manager invites (mutually exclusive with team_id)';

-- Update schema version
SELECT add_schema_version('1.2.0', 'add_club_manager_role', 'Add club_manager role for club-level management, remove unused user role, add club_id to invitations');
