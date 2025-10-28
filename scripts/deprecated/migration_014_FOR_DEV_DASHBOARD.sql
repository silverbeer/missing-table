-- Add audit trail fields to games table
-- Track who created/updated games and the source (manual, match-scraper, import)
--
-- SAFE FOR DEV: This migration only adds columns - no data loss risk
-- Run this in Supabase Dashboard SQL Editor

-- Add audit columns to games table
ALTER TABLE games
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual';

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_games_updated_by ON games(updated_by);
CREATE INDEX IF NOT EXISTS idx_games_created_by ON games(created_by);
CREATE INDEX IF NOT EXISTS idx_games_source ON games(source);

-- Add comments for documentation
COMMENT ON COLUMN games.created_by IS 'User ID who created the game (match-scraper service account for legacy data)';
COMMENT ON COLUMN games.updated_by IS 'User ID who last updated the game';
COMMENT ON COLUMN games.source IS 'Source of game data: manual, match-scraper, import, etc.';

-- Migration complete!
-- Next step: Run setup_audit_trail.py to create service account and backfill data
