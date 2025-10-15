-- Migration: Update match_status from 'played' to 'completed'
-- Created: 2024-10-14
-- Description: Updates the match_status CHECK constraint and migrates existing data

-- Step 1: Update any existing matches with status 'played' to 'completed'
UPDATE matches
SET match_status = 'completed'
WHERE match_status = 'played';

-- Step 2: Drop the old CHECK constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

-- Step 3: Add new CHECK constraint with 'completed' instead of 'played'
ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));

-- Step 4: Update the default value comment (informational only)
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled, live, completed, postponed, cancelled';
