-- Add game status field to properly track game states
-- This enables accurate standings by only counting 'played' games

-- Create enum type for game status
CREATE TYPE game_status AS ENUM ('scheduled', 'played', 'postponed', 'cancelled');

-- Add status column to games table
ALTER TABLE games
ADD COLUMN status game_status NOT NULL DEFAULT 'scheduled';

-- Add index for performance on status queries
CREATE INDEX idx_games_status ON games(status);

-- Add composite index for common queries (status + other filters)
CREATE INDEX idx_games_status_filters ON games(status, season_id, age_group_id, division_id);

-- Update existing games based on date logic:
-- - Games in the past (≤ today) should be marked as 'played'
-- - Games in the future (> today) should remain 'scheduled'
UPDATE games
SET status = CASE
    WHEN game_date <= CURRENT_DATE THEN 'played'::game_status
    ELSE 'scheduled'::game_status
END;

-- Add comments for documentation
COMMENT ON COLUMN games.status IS 'Current status of the game: scheduled (future), played (completed), postponed (delayed), cancelled (not happening)';
COMMENT ON TYPE game_status IS 'Enum for tracking game states throughout their lifecycle';
COMMENT ON INDEX idx_games_status IS 'Index for filtering games by status (performance optimization for standings)';
COMMENT ON INDEX idx_games_status_filters IS 'Composite index for common status + filter queries';