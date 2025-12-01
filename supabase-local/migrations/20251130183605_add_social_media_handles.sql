-- Add social media handle fields to user_profiles
-- These store the username/handle only (not full URLs)

ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS instagram_handle VARCHAR(30),
ADD COLUMN IF NOT EXISTS snapchat_handle VARCHAR(30),
ADD COLUMN IF NOT EXISTS tiktok_handle VARCHAR(30);

-- Add comments for documentation
COMMENT ON COLUMN user_profiles.instagram_handle IS 'Instagram username (without @)';
COMMENT ON COLUMN user_profiles.snapchat_handle IS 'Snapchat username';
COMMENT ON COLUMN user_profiles.tiktok_handle IS 'TikTok username (without @)';
