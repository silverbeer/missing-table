-- Migration: Add automatic updated_at trigger for matches table
-- Description: Automatically update the updated_at timestamp whenever a match is modified
-- Date: 2025-11-09
-- Related Issue: Match scores were updating but updated_at timestamp remained at creation time

-- Step 1: Ensure moddatetime extension is enabled
-- This extension provides the automatic timestamp update functionality
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- Step 2: Fix match_status constraint to include all statuses used by the application
-- The application uses 'tbd' and 'completed' but they weren't in the constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'tbd', 'live', 'completed', 'played', 'postponed', 'cancelled'));

-- Step 3: Create trigger to automatically update updated_at timestamp
-- This trigger fires BEFORE any UPDATE operation on the matches table
-- The moddatetime function updates the specified column (updated_at) to the current timestamp
CREATE TRIGGER handle_updated_at
  BEFORE UPDATE ON matches
  FOR EACH ROW
  EXECUTE PROCEDURE moddatetime(updated_at);

-- Update column comments for clarity
COMMENT ON COLUMN matches.match_status IS 'Match status: scheduled (default), tbd (time to be determined), live (in progress), completed (finished with scores), played (legacy status), postponed, or cancelled';
COMMENT ON COLUMN matches.updated_at IS 'Automatically updated timestamp - managed by database trigger';
