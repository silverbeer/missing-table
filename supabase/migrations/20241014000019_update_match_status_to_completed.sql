-- Migration: Add match_status column and update from 'played' to 'completed'
-- Created: 2024-10-14
-- Description: Adds match_status column if it doesn't exist, updates CHECK constraint and migrates existing data

-- Step 1: Add match_status column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'public'
                   AND table_name = 'matches'
                   AND column_name = 'match_status') THEN
        ALTER TABLE matches
        ADD COLUMN match_status VARCHAR(20) DEFAULT 'scheduled'
        CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));

        RAISE NOTICE 'Added match_status column to matches table';
    END IF;
END $$;

-- Step 2: Update any existing matches with status 'played' to 'completed' (if column exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
               AND table_name = 'matches'
               AND column_name = 'match_status') THEN
        UPDATE matches
        SET match_status = 'completed'
        WHERE match_status = 'played';
    END IF;
END $$;

-- Step 3: Drop the old CHECK constraint if it exists
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

-- Step 4: Add new CHECK constraint with 'completed' instead of 'played'
ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));

-- Step 5: Update the default value comment (informational only)
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled, live, completed, postponed, cancelled';
