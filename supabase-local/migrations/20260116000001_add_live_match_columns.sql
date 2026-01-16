-- Migration: Add live match clock columns to matches table
-- These timestamp columns allow client-side clock calculation for live matches

ALTER TABLE matches
ADD COLUMN IF NOT EXISTS kickoff_time TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS halftime_start TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS second_half_start TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS match_end_time TIMESTAMPTZ;

-- Add comment explaining the columns
COMMENT ON COLUMN matches.kickoff_time IS 'Timestamp when the match kicked off (1st half started)';
COMMENT ON COLUMN matches.halftime_start IS 'Timestamp when halftime began';
COMMENT ON COLUMN matches.second_half_start IS 'Timestamp when 2nd half kicked off';
COMMENT ON COLUMN matches.match_end_time IS 'Timestamp when the match ended';

-- Create index for efficient live match queries
CREATE INDEX IF NOT EXISTS idx_matches_live_status
ON matches(match_status) WHERE match_status = 'live';
