-- Fix RLS policies for matches table after games→matches rename
-- Issue: Table was renamed but RLS policies were not migrated
-- This prevents team managers from updating their team's matches

-- ============================================================================
-- PART 1: Drop old game policies if they still reference wrong table
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
-- PART 2: Ensure helper functions exist and handle both role formats
-- ============================================================================

-- Update is_team_manager to handle both 'team_manager' and 'team-manager'
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

COMMENT ON POLICY "team_manager_update_matches" ON matches IS
'Allows team managers to update matches where their team is home or away. Fixed after games→matches rename.';

COMMENT ON POLICY "team_manager_insert_matches" ON matches IS
'Allows team managers to create matches for their teams. Fixed after games→matches rename.';

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
DECLARE
    policy_count INTEGER;
BEGIN
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
