-- Backfill club_id for roster-managed players
-- Players added via the roster manager (POST /api/admin/players/{player_id}/teams)
-- get player_team_history entries but their user_profiles.club_id is never set.
-- This causes them to see unrelated clubs/leagues in the UI.

UPDATE user_profiles up
SET club_id = t.club_id
FROM player_team_history pth
JOIN teams t ON pth.team_id = t.id
WHERE up.id = pth.player_id
  AND up.club_id IS NULL
  AND pth.is_current = true
  AND t.club_id IS NOT NULL;
