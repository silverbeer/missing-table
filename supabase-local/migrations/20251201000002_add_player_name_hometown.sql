-- ============================================================================
-- ADD PLAYER NAME AND HOMETOWN FIELDS
-- ============================================================================
-- Purpose: Add first_name, last_name, hometown to user_profiles
--          display_name remains for creative/fun display (emojis, numbers, etc.)
-- Author: Claude Code
-- Date: 2025-12-01
-- ============================================================================

-- Add new columns to user_profiles
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS hometown VARCHAR(200);

-- Add comment to clarify display_name purpose
COMMENT ON COLUMN user_profiles.display_name IS 'Creative display name for fun - can include emojis, numbers, nicknames';
COMMENT ON COLUMN user_profiles.first_name IS 'Player real first name';
COMMENT ON COLUMN user_profiles.last_name IS 'Player real last name';
COMMENT ON COLUMN user_profiles.hometown IS 'Player hometown/city';
