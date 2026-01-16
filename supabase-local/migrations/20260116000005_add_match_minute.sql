-- Add match_minute column to track when goals are scored
-- Format: integer for regular time (22 for 22'), NULL for events without time
-- Stoppage time stored as base minute (45 or 90) with extra_time column

ALTER TABLE match_events
ADD COLUMN IF NOT EXISTS match_minute INTEGER,
ADD COLUMN IF NOT EXISTS extra_time INTEGER DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN match_events.match_minute IS 'Minute when event occurred (e.g., 22 for 22nd minute)';
COMMENT ON COLUMN match_events.extra_time IS 'Stoppage/injury time minutes (e.g., 5 for 90+5)';
