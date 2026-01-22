-- Migration: Add scheduled_kickoff column to matches table
--
-- This adds a new column for the scheduled kickoff datetime (stored in UTC).
-- This is different from `kickoff_time` which tracks when a live match actually started.

-- Add the scheduled_kickoff column
ALTER TABLE matches ADD COLUMN IF NOT EXISTS scheduled_kickoff TIMESTAMPTZ;

-- Add comment explaining the column's purpose
COMMENT ON COLUMN matches.scheduled_kickoff IS
  'Scheduled kickoff datetime in UTC. Different from kickoff_time which tracks when live match actually started.';
