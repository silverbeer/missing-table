-- ============================================================================
-- ADD CLUB BRANDING COLUMNS (LOGO AND COLORS)
-- ============================================================================
-- Purpose: Add logo_url, primary_color, and secondary_color to clubs table
-- Impact: Enables club branding customization
-- Author: Claude Code
-- Date: 2025-11-24
-- ============================================================================

-- Add logo_url column for club logo images (stored in Supabase Storage)
ALTER TABLE clubs ADD COLUMN IF NOT EXISTS logo_url TEXT;

-- Add primary_color column with neutral gray default
ALTER TABLE clubs ADD COLUMN IF NOT EXISTS primary_color TEXT DEFAULT '#6B7280';

-- Add secondary_color column with darker gray default
ALTER TABLE clubs ADD COLUMN IF NOT EXISTS secondary_color TEXT DEFAULT '#374151';

-- Add comments for documentation
COMMENT ON COLUMN clubs.logo_url IS 'URL to club logo image stored in Supabase Storage (club-logos bucket)';
COMMENT ON COLUMN clubs.primary_color IS 'Primary brand color as hex code (e.g., #FFD700 for gold)';
COMMENT ON COLUMN clubs.secondary_color IS 'Secondary brand color as hex code (e.g., #1E3A5F for dark blue)';

-- Update existing clubs to have default colors (for clubs where column was NULL before)
UPDATE clubs SET primary_color = '#6B7280' WHERE primary_color IS NULL;
UPDATE clubs SET secondary_color = '#374151' WHERE secondary_color IS NULL;

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.4.0',
    '20251124000001_add_club_branding_columns',
    'Add logo_url, primary_color, and secondary_color columns to clubs table for branding'
);
