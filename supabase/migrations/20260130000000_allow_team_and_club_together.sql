-- Allow user_profiles to have both team_id and club_id
--
-- The old constraint (chk_team_or_club_not_both) enforced that a user could have
-- either team_id OR club_id, but not both. This is incorrect: players belong to
-- teams, and teams belong to clubs. Both should be set when the team has a parent club.

-- Drop the overly restrictive constraint
ALTER TABLE user_profiles
DROP CONSTRAINT IF EXISTS chk_team_or_club_not_both;

-- Backfill club_id for users who have a team_id but no club_id
-- Derives the club from the team's parent club
UPDATE user_profiles up
SET club_id = t.club_id
FROM teams t
WHERE t.id = up.team_id
  AND up.club_id IS NULL
  AND t.club_id IS NOT NULL;

-- Update column comment to reflect new behavior
COMMENT ON COLUMN user_profiles.club_id IS 'Club ID derived from the user''s team, or set directly for club-level roles. Users with a team_id will typically also have club_id set to the team''s parent club.';

-- Update schema version
SELECT add_schema_version('1.6.0', 'allow_team_and_club_together', 'Drop chk_team_or_club_not_both constraint; backfill club_id from team parent club');
