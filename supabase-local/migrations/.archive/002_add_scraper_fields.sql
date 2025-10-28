-- Add scraper integration fields to games table
-- Migration: Add match scraper support fields

-- Add new columns to games table
ALTER TABLE games
ADD COLUMN mls_match_id BIGINT NULL,
ADD COLUMN data_source VARCHAR(20) DEFAULT 'manual',
ADD COLUMN last_scraped_at TIMESTAMP WITH TIME ZONE NULL,
ADD COLUMN score_locked BOOLEAN DEFAULT FALSE;

-- Add indexes for performance
CREATE INDEX idx_games_mls_match_id ON games(mls_match_id);
CREATE INDEX idx_games_data_source ON games(data_source);

-- Add unique constraint on mls_match_id (only for non-null values)
CREATE UNIQUE INDEX idx_games_mls_match_id_unique ON games(mls_match_id) WHERE mls_match_id IS NOT NULL;

-- Add check constraint for data_source values
ALTER TABLE games ADD CONSTRAINT chk_games_data_source
CHECK (data_source IN ('manual', 'mls_scraper'));

-- Update existing games to have manual data source
UPDATE games SET data_source = 'manual' WHERE data_source IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN games.mls_match_id IS 'MLS Next match identifier for scraped games (e.g., 98667)';
COMMENT ON COLUMN games.data_source IS 'Source of game data: manual (team admin) or mls_scraper';
COMMENT ON COLUMN games.last_scraped_at IS 'Timestamp when scraper last updated this game';
COMMENT ON COLUMN games.score_locked IS 'Prevents scraper from overwriting manually entered scores';