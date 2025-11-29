-- ============================================================================
-- ADD PLAYER PROFILE PHOTOS AND CUSTOMIZATION
-- ============================================================================
-- Purpose: Allow players to upload up to 3 profile photos with customizable
--          overlays showing their number and position
-- Impact: Adds columns to user_profiles, creates player-photos storage bucket
-- Author: Claude Code
-- Date: 2025-11-29
-- ============================================================================

-- ============================================================================
-- USER PROFILES COLUMNS
-- ============================================================================

-- Photo URLs (3 slots)
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS photo_1_url TEXT,
ADD COLUMN IF NOT EXISTS photo_2_url TEXT,
ADD COLUMN IF NOT EXISTS photo_3_url TEXT;

-- Which photo slot is the profile picture (1, 2, or 3)
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS profile_photo_slot INTEGER CHECK (profile_photo_slot IS NULL OR profile_photo_slot IN (1, 2, 3));

-- Overlay style preference
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS overlay_style VARCHAR(20) DEFAULT 'badge' CHECK (overlay_style IN ('badge', 'jersey', 'caption', 'none'));

-- Color customization (hex values)
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS primary_color VARCHAR(7) DEFAULT '#3B82F6',
ADD COLUMN IF NOT EXISTS text_color VARCHAR(7) DEFAULT '#FFFFFF',
ADD COLUMN IF NOT EXISTS accent_color VARCHAR(7) DEFAULT '#1D4ED8';

-- ============================================================================
-- PLAYER-PHOTOS STORAGE BUCKET
-- ============================================================================

-- Create the player-photos storage bucket (public, with size/type limits)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('player-photos', 'player-photos', true, 512000, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE SET
    public = true,
    file_size_limit = 512000,
    allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp'];

-- ============================================================================
-- STORAGE POLICIES
-- ============================================================================

-- Allow anyone to view player photos (public bucket)
CREATE POLICY "Player photos are publicly accessible"
ON storage.objects FOR SELECT
USING (bucket_id = 'player-photos');

-- Allow authenticated users to upload their own photos
-- File path format: {user_id}/photo_{slot}.{ext}
CREATE POLICY "Players can upload own photos"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'player-photos'
    AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Allow authenticated users to update their own photos
CREATE POLICY "Players can update own photos"
ON storage.objects FOR UPDATE
TO authenticated
USING (
    bucket_id = 'player-photos'
    AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Allow authenticated users to delete their own photos
CREATE POLICY "Players can delete own photos"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'player-photos'
    AND auth.uid()::text = (storage.foldername(name))[1]
);

-- Allow service role (backend) to manage all player photos
-- This is required because backend uses service key which doesn't populate auth.uid()
CREATE POLICY "Service role can manage player photos"
ON storage.objects
FOR ALL
TO service_role
USING (bucket_id = 'player-photos')
WITH CHECK (bucket_id = 'player-photos');

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.5.0',
    '20251129000001_add_player_photos',
    'Add player profile photos with customizable overlays and colors'
);
