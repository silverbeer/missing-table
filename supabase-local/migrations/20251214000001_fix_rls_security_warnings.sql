-- Migration: Fix Supabase Security Advisor Warnings
-- Description: Addresses 4 security warnings from Supabase Security Advisor:
--   1. Policy Exists RLS Disabled - user_profiles (policies exist but RLS disabled)
--   2. Security Definer View - teams_with_details (owned by postgres, no explicit security)
--   3. RLS Disabled in Public - schema_version (no RLS on public table)
--   4. RLS Disabled in Public - user_profiles (same as #1)

-- ============================================================================
-- FIX 1: Enable RLS on user_profiles
-- Policies already exist (from migration 011), just need to enable RLS
-- The is_admin() function is SECURITY DEFINER which prevents recursion
-- ============================================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Also need to add a policy for service_role to insert profiles (for handle_new_user trigger)
-- Check if it exists first to make idempotent
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polrelid = 'public.user_profiles'::regclass
        AND polname = 'service_role_insert_profiles'
    ) THEN
        CREATE POLICY "service_role_insert_profiles" ON user_profiles
            FOR INSERT
            TO service_role
            WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polrelid = 'public.user_profiles'::regclass
        AND polname = 'service_role_manage_profiles'
    ) THEN
        CREATE POLICY "service_role_manage_profiles" ON user_profiles
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

-- ============================================================================
-- FIX 2: Recreate teams_with_details view with explicit SECURITY INVOKER
-- This explicitly tells Postgres to use the querying user's permissions
-- ============================================================================

-- Drop and recreate with explicit security setting
DROP VIEW IF EXISTS teams_with_details;

CREATE VIEW teams_with_details
WITH (security_invoker = true)
AS
SELECT
    t.id,
    t.name AS team_name,
    t.city,
    t.academy_team,
    c.id AS club_id,
    c.name AS club_name,
    c.city AS club_city,
    l.id AS league_id,
    l.name AS league_name,
    l.description AS league_description,
    t.created_at,
    t.updated_at
FROM teams t
LEFT JOIN clubs c ON t.club_id = c.id
JOIN leagues l ON t.league_id = l.id;

COMMENT ON VIEW teams_with_details IS
'Convenient view showing teams with their club and league information. Uses SECURITY INVOKER to respect RLS.';

-- Re-grant access to the view
GRANT SELECT ON teams_with_details TO authenticated;
GRANT SELECT ON teams_with_details TO anon;

-- ============================================================================
-- FIX 3: Enable RLS on schema_version table
-- This is a metadata table - should be readable by everyone but writable only by migrations
-- ============================================================================

ALTER TABLE schema_version ENABLE ROW LEVEL SECURITY;

-- Allow everyone to read schema version (it's public metadata)
CREATE POLICY "anon_read_schema_version" ON schema_version
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "authenticated_read_schema_version" ON schema_version
    FOR SELECT
    TO authenticated
    USING (true);

-- Only service_role can insert (used by migrations)
CREATE POLICY "service_role_manage_schema_version" ON schema_version
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.7.0',
    '20251214000001_fix_rls_security_warnings',
    'Fix Supabase Security Advisor warnings: enable RLS on user_profiles and schema_version, add SECURITY INVOKER to teams_with_details view'
);
