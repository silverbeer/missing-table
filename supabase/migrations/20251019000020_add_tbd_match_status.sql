-- Migration: Add 'tbd' status to match_status CHECK constraint
-- Created: 2025-10-19
-- Description: Adds 'tbd' (to be determined) status for matches that have been played
--              but scores are not yet available from the source system (mlssoccer.com)
--
-- This enables match-scraper to set status='tbd' when a match shows as played
-- but no final score is posted yet. The status will be updated to 'completed'
-- once scores become available.
--
-- Status flow: scheduled → tbd → completed
--              (or direct: scheduled → completed if score available immediately)

-- Step 1: Drop the existing CHECK constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

-- Step 2: Add new CHECK constraint with 'tbd' included
ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'tbd', 'live', 'completed', 'postponed', 'cancelled'));

-- Step 3: Create index for tbd status queries (optional, for performance)
CREATE INDEX IF NOT EXISTS idx_matches_tbd_status
ON matches(match_status)
WHERE match_status = 'tbd';

-- Step 4: Update column comment to document the new status
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled, tbd (match played, score pending), live, completed, postponed, cancelled';

-- Step 5: Add informational comments
COMMENT ON CONSTRAINT matches_match_status_check ON matches IS 'Ensures match_status is one of the valid status values. tbd = match played but score not yet available.';
