-- Migration: Fix player_team_history RLS policy for admin inserts
-- Description: Adds missing INSERT/UPDATE/DELETE policy for admins
--
-- Problem: Admins could only SELECT from player_team_history, not INSERT
-- Error: "new row violates row-level security policy for table player_team_history"

-- ============================================================================
-- FIX: Add admin management policy for player_team_history
-- ============================================================================

-- Drop existing read-only admin policy if it exists
DROP POLICY IF EXISTS "Admins can view all history" ON player_team_history;

-- Create comprehensive admin policy (SELECT, INSERT, UPDATE, DELETE)
CREATE POLICY "Admins can manage all history" ON player_team_history
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.7.1',
    '20251214000002_fix_player_team_history_rls',
    'Fix player_team_history RLS: add admin INSERT/UPDATE/DELETE policy'
);
