-- PRODUCTION FIX: RLS policies for matches table (COMPLETE - includes all prerequisites)
-- Date: 2025-10-18
-- Issue: Team managers cannot update matches - "no rows affected" error
-- Root Cause: Helper functions (is_admin, manages_team) missing in production
-- This file includes ALL prerequisites - safe to run on production

-- ============================================================================
-- PART 1: Create helper functions (prerequisites for RLS policies)
-- ============================================================================

-- Function to check if current user is admin (uses service role to avoid recursion)
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
DECLARE
    user_role TEXT;
BEGIN
    -- Return false if no authenticated user
    IF auth.uid() IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Get user role directly without RLS context
    SELECT role INTO user_role
    FROM public.user_profiles
    WHERE id = auth.uid();

    RETURN user_role = 'admin';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if current user is a team manager
-- Updated to handle both 'team_manager' and 'team-manager' formats
CREATE OR REPLACE FUNCTION public.is_team_manager()
RETURNS BOOLEAN AS $$
DECLARE
    user_role TEXT;
BEGIN
    IF auth.uid() IS NULL THEN
        RETURN FALSE;
    END IF;

    SELECT role INTO user_role
    FROM public.user_profiles
    WHERE id = auth.uid();

    -- Handle both formats for compatibility
    RETURN user_role IN ('team_manager', 'team-manager');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user manages a specific team
CREATE OR REPLACE FUNCTION public.manages_team(team_id_param INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    IF auth.uid() IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Check team_manager_assignments table
    RETURN EXISTS (
        SELECT 1 FROM public.team_manager_assignments
        WHERE user_id = auth.uid()
        AND team_id = team_id_param
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- PART 2: Drop old policies if they exist
-- ============================================================================

DO $$
BEGIN
    -- Drop any old 'games' policies that might exist on matches table
    DROP POLICY IF EXISTS "anon_read_games" ON matches;
    DROP POLICY IF EXISTS "authenticated_read_games" ON matches;
    DROP POLICY IF EXISTS "admin_all_games" ON matches;
    DROP POLICY IF EXISTS "team_manager_insert_games" ON matches;
    DROP POLICY IF EXISTS "team_manager_update_games" ON matches;

    -- Drop any existing matches policies to start fresh
    DROP POLICY IF EXISTS "anon_read_matches" ON matches;
    DROP POLICY IF EXISTS "authenticated_read_matches" ON matches;
    DROP POLICY IF EXISTS "admin_all_matches" ON matches;
    DROP POLICY IF EXISTS "team_manager_insert_matches" ON matches;
    DROP POLICY IF EXISTS "team_manager_update_matches" ON matches;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'Matches table does not exist yet';
    WHEN undefined_object THEN
        RAISE NOTICE 'Some policies do not exist, continuing...';
END $$;

-- ============================================================================
-- PART 3: Enable RLS on matches table (if not already enabled)
-- ============================================================================

ALTER TABLE matches ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- PART 4: Create RLS policies for matches table
-- ============================================================================

-- Allow public (anonymous) read access
CREATE POLICY "anon_read_matches" ON matches
    FOR SELECT
    TO anon
    USING (true);

-- Allow authenticated users to read all matches
CREATE POLICY "authenticated_read_matches" ON matches
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow admins full access to all matches
CREATE POLICY "admin_all_matches" ON matches
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- Allow team managers to INSERT matches for their teams
CREATE POLICY "team_manager_insert_matches" ON matches
    FOR INSERT
    TO authenticated
    WITH CHECK (
        is_team_manager() AND (
            manages_team(home_team_id) OR manages_team(away_team_id)
        )
    );

-- Allow team managers to UPDATE matches for their teams
CREATE POLICY "team_manager_update_matches" ON matches
    FOR UPDATE
    TO authenticated
    USING (
        is_team_manager() AND (
            manages_team(home_team_id) OR manages_team(away_team_id)
        )
    )
    WITH CHECK (
        is_team_manager() AND (
            manages_team(home_team_id) OR manages_team(away_team_id)
        )
    );

-- ============================================================================
-- PART 5: Grant necessary permissions
-- ============================================================================

-- Ensure authenticated role can perform operations
GRANT SELECT, INSERT, UPDATE, DELETE ON matches TO authenticated;

-- Ensure anon role can read
GRANT SELECT ON matches TO anon;

-- ============================================================================
-- PART 6: Add comments for documentation
-- ============================================================================

COMMENT ON FUNCTION public.is_admin() IS
'Helper function to check if current user is admin. Uses SECURITY DEFINER to avoid RLS recursion.';

COMMENT ON FUNCTION public.is_team_manager() IS
'Helper function to check if current user is a team manager. Handles both team_manager and team-manager role formats.';

COMMENT ON FUNCTION public.manages_team(INTEGER) IS
'Helper function to check if current user manages a specific team via team_manager_assignments.';

COMMENT ON POLICY "team_manager_update_matches" ON matches IS
'Allows team managers to update matches where their team is home or away. Fixed after games→matches rename.';

COMMENT ON POLICY "team_manager_insert_matches" ON matches IS
'Allows team managers to create matches for their teams. Fixed after games→matches rename.';

-- ============================================================================
-- PART 7: Verification
-- ============================================================================

DO $$
DECLARE
    policy_count INTEGER;
    function_exists BOOLEAN;
BEGIN
    -- Check helper functions
    SELECT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'is_admin' AND pronamespace = 'public'::regnamespace
    ) INTO function_exists;

    IF function_exists THEN
        RAISE NOTICE '✓ Helper function is_admin() exists';
    ELSE
        RAISE WARNING '✗ Helper function is_admin() missing';
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'manages_team' AND pronamespace = 'public'::regnamespace
    ) INTO function_exists;

    IF function_exists THEN
        RAISE NOTICE '✓ Helper function manages_team() exists';
    ELSE
        RAISE WARNING '✗ Helper function manages_team() missing';
    END IF;

    -- Check policies
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'matches';

    RAISE NOTICE 'RLS policies on matches table: %', policy_count;

    IF policy_count < 5 THEN
        RAISE WARNING 'Expected at least 5 policies, found %', policy_count;
    ELSE
        RAISE NOTICE '✓ RLS policies successfully created for matches table';
    END IF;
END $$;
