-- Migration: Remove unused mls_match_id column
--
-- Problem: The matches table has both mls_match_id (bigint) and match_id (text) columns.
--          Only match_id is actually used - it contains the external MLS match IDs.
--          mls_match_id is completely unused and always NULL for all 240 match-scraper matches.
--
-- Solution: Drop the unused mls_match_id column and its associated index.
--
-- Impact:
--   - Removes unused column from matches table
--   - Removes unused index idx_matches_mls_match_id
--   - No data loss (column is 100% NULL)
--   - Simplifies schema and reduces confusion

-- Step 1: Drop the index on mls_match_id
DROP INDEX IF EXISTS idx_matches_mls_match_id;

-- Step 2: Drop the mls_match_id column
ALTER TABLE matches
DROP COLUMN IF EXISTS mls_match_id;

-- Add helpful comment on match_id to clarify it's the one to use
COMMENT ON COLUMN matches.match_id IS 'External match ID from match-scraper service (e.g., MLS match ID). This is the primary external identifier.';
