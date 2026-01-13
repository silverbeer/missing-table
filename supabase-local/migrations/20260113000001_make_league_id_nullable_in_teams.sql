-- Make league_id nullable in teams table to support guest/tournament teams
-- Guest teams (friendlies only) and tournament teams don't need a league assignment

-- Alter the teams table to make league_id nullable
ALTER TABLE teams
ALTER COLUMN league_id DROP NOT NULL;

-- Add a comment explaining when league_id can be null
COMMENT ON COLUMN teams.league_id IS 'League ID - required for league teams, optional for guest/tournament teams';

-- Also make division_id nullable for consistency
ALTER TABLE teams
ALTER COLUMN division_id DROP NOT NULL;

COMMENT ON COLUMN teams.division_id IS 'Division ID - required for league teams, optional for guest/tournament teams';
