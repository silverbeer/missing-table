-- Sync dev schema with prod schema
-- Add missing columns to matches table

-- Add scraper integration fields
ALTER TABLE matches
ADD COLUMN IF NOT EXISTS mls_match_id BIGINT NULL,
ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) DEFAULT 'manual',
ADD COLUMN IF NOT EXISTS last_scraped_at TIMESTAMP WITH TIME ZONE NULL,
ADD COLUMN IF NOT EXISTS score_locked BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS created_by UUID NULL,
ADD COLUMN IF NOT EXISTS updated_by UUID NULL,
ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual';

-- Add indexes for performance (if they don't exist)
CREATE INDEX IF NOT EXISTS idx_matches_mls_match_id ON matches(mls_match_id);
CREATE INDEX IF NOT EXISTS idx_matches_data_source ON matches(data_source);

-- Add unique constraint on mls_match_id (only for non-null values)
DROP INDEX IF EXISTS idx_matches_mls_match_id_unique;
CREATE UNIQUE INDEX idx_matches_mls_match_id_unique ON matches(mls_match_id) WHERE mls_match_id IS NOT NULL;

-- Add check constraint for data_source values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_matches_data_source'
    ) THEN
        ALTER TABLE matches ADD CONSTRAINT chk_matches_data_source
        CHECK (data_source IN ('manual', 'mls_scraper'));
    END IF;
END $$;

-- Update existing matches to have manual data source
UPDATE matches SET data_source = 'manual' WHERE data_source IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN matches.mls_match_id IS 'MLS Next match identifier for scraped matches (e.g., 98667)';
COMMENT ON COLUMN matches.data_source IS 'Source of match data: manual (team admin) or mls_scraper';
COMMENT ON COLUMN matches.last_scraped_at IS 'Timestamp when scraper last updated this match';
COMMENT ON COLUMN matches.score_locked IS 'Prevents scraper from overwriting manually entered scores';
COMMENT ON COLUMN matches.created_by IS 'User ID who created this match';
COMMENT ON COLUMN matches.updated_by IS 'User ID who last updated this match';
COMMENT ON COLUMN matches.source IS 'Source of the match data (manual or match-scraper)';
