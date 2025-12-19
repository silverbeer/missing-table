-- Migration: Add OAuth Support to user_profiles
-- Description: Add columns needed for Google OAuth and other social login providers
-- Version: 1.2.0

-- Add auth_provider column to track how user signed up
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50) DEFAULT 'password';

-- Add profile_photo_url for OAuth avatar photos
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS profile_photo_url TEXT;

-- Add comment explaining the columns
COMMENT ON COLUMN user_profiles.auth_provider IS 'Authentication provider: password, google, github, etc.';
COMMENT ON COLUMN user_profiles.profile_photo_url IS 'URL to user profile photo (from OAuth provider or uploaded)';

-- Update schema version
SELECT add_schema_version('1.2.0', 'add_oauth_support', 'Add OAuth support columns for social login');
