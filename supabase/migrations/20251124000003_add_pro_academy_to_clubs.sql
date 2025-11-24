-- ============================================================================
-- ADD PRO ACADEMY FLAG TO CLUBS
-- ============================================================================
-- Purpose: Add pro_academy column to clubs table to distinguish pro academies
-- Impact: Enables Pro Academy badge display on club tiles
-- Author: Claude Code
-- Date: 2025-11-24
-- ============================================================================

ALTER TABLE clubs ADD COLUMN IF NOT EXISTS pro_academy BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN clubs.pro_academy IS 'Indicates if this club is a professional academy';

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.4.2',
    '20251124000003_add_pro_academy_to_clubs',
    'Add pro_academy flag to clubs table'
);
