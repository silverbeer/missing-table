-- Add status column to games table
ALTER TABLE games
ADD COLUMN status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'played', 'postponed', 'cancelled'));

-- Add index for performance
CREATE INDEX idx_games_status ON games(status);

-- Update existing games to have 'played' status if they have scores
UPDATE games
SET status = 'played'
WHERE home_score IS NOT NULL AND away_score IS NOT NULL AND home_score > 0 OR away_score > 0;

-- Comment explaining the column
COMMENT ON COLUMN games.status IS 'Game status: scheduled (default), played, postponed, or cancelled';
