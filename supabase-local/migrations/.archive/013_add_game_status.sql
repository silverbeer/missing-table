-- Add match_status column to games table
ALTER TABLE games
ADD COLUMN match_status VARCHAR(20) DEFAULT 'scheduled' CHECK (match_status IN ('scheduled', 'played', 'postponed', 'cancelled'));

-- Add index for performance
CREATE INDEX idx_games_match_status ON games(match_status);

-- Update existing games played before 10/3/2025 to have 'played' status
UPDATE games
SET match_status = 'played'
WHERE game_date < '2025-10-03';

-- Comment explaining the column
COMMENT ON COLUMN games.match_status IS 'Game status: scheduled (default), played, postponed, or cancelled';
