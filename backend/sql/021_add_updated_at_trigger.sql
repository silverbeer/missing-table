-- Migration: Add automatic updated_at trigger for matches table
-- Description: Automatically update the updated_at timestamp whenever a match is modified
-- Date: 2025-11-09
-- Related Issue: Match scores were updating but updated_at timestamp remained at creation time

-- Step 1: Ensure moddatetime extension is enabled
-- This extension provides the automatic timestamp update functionality
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- Step 2: Add 'played' to match_status ENUM if it doesn't exist
-- Note: match_status is an ENUM type, not a VARCHAR with CHECK constraint
-- Check if 'played' value exists, if not add it
DO $$
BEGIN
    -- Check if 'played' is already in the ENUM
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'played'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'match_status')
    ) THEN
        -- Add 'played' to the ENUM
        ALTER TYPE match_status ADD VALUE IF NOT EXISTS 'played';
    END IF;
END$$;

-- Step 3: Create trigger to automatically update updated_at timestamp
-- This trigger fires BEFORE any UPDATE operation on the matches table
-- The moddatetime function updates the specified column (updated_at) to the current timestamp
DROP TRIGGER IF EXISTS handle_updated_at ON matches;
CREATE TRIGGER handle_updated_at
  BEFORE UPDATE ON matches
  FOR EACH ROW
  EXECUTE PROCEDURE moddatetime(updated_at);

-- Update column comments for clarity
COMMENT ON COLUMN matches.match_status IS 'Match status ENUM: scheduled (default), tbd (time to be determined), live (in progress), completed (finished with scores), played (legacy status), postponed, or cancelled';
COMMENT ON COLUMN matches.updated_at IS 'Automatically updated timestamp - managed by database trigger';
