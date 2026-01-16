-- Add half_duration column to matches table
-- Stores the duration of each half in minutes (default 45 for 90-minute games)

ALTER TABLE matches
ADD COLUMN IF NOT EXISTS half_duration INTEGER DEFAULT 45;

COMMENT ON COLUMN matches.half_duration IS 'Duration of each half in minutes (e.g., 45 for 90-min game, 40 for 80-min game)';
