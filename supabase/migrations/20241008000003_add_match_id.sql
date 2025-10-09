-- Add match_id field for external match tracking (like match-scraper)
-- and improve duplicate prevention

-- Add match_id column for external system tracking
ALTER TABLE games
ADD COLUMN IF NOT EXISTS match_id TEXT NULL;

-- Create index for match_id lookups
CREATE INDEX IF NOT EXISTS idx_games_match_id ON games(match_id) WHERE match_id IS NOT NULL;

-- Create composite unique constraint to prevent true duplicates
-- (same teams, date, season, age group, game type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_games_unique_match ON games(
    game_date,
    home_team_id,
    away_team_id,
    season_id,
    age_group_id,
    game_type_id
) WHERE match_id IS NULL;

-- Create separate unique constraint for external matches with match_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_games_unique_external_match ON games(match_id)
WHERE match_id IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN games.match_id IS 'External match identifier from systems like match-scraper. NULL for manually created games.';
COMMENT ON INDEX idx_games_unique_match IS 'Prevents duplicate games for the same teams, date, season, age group, and game type';
COMMENT ON INDEX idx_games_unique_external_match IS 'Ensures external match IDs are unique across the system';
