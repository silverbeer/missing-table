-- ============================================================================
-- CREATE CLUB-LOGOS STORAGE BUCKET
-- ============================================================================
-- Purpose: Create storage bucket for club logo images
-- Impact: Enables logo upload functionality
-- Author: Claude Code
-- Date: 2025-11-24
-- ============================================================================

-- Create the club-logos storage bucket
-- Note: file_size_limit and allowed_mime_types are handled in application code
INSERT INTO storage.buckets (id, name)
VALUES ('club-logos', 'club-logos')
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- STORAGE POLICIES
-- ============================================================================

-- Allow anyone to view club logos (public bucket)
CREATE POLICY "Club logos are publicly accessible"
ON storage.objects FOR SELECT
USING (bucket_id = 'club-logos');

-- Allow authenticated admins to upload club logos
CREATE POLICY "Admins can upload club logos"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
    bucket_id = 'club-logos'
    AND is_admin()
);

-- Allow authenticated admins to update club logos
CREATE POLICY "Admins can update club logos"
ON storage.objects FOR UPDATE
TO authenticated
USING (
    bucket_id = 'club-logos'
    AND is_admin()
);

-- Allow authenticated admins to delete club logos
CREATE POLICY "Admins can delete club logos"
ON storage.objects FOR DELETE
TO authenticated
USING (
    bucket_id = 'club-logos'
    AND is_admin()
);

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.4.1',
    '20251124000002_create_club_logos_storage_bucket',
    'Create club-logos storage bucket for club logo images'
);
