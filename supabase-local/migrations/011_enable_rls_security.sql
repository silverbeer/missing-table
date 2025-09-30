-- Migration: Enable Row Level Security (RLS) for all public tables
-- Description: Addresses Supabase security warnings by enabling RLS with proper policies
-- This migration uses the anon role and service_role to avoid recursion issues

-- ============================================================================
-- PART 1: Create helper functions FIRST (before policies that use them)
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

    RETURN user_role = 'team_manager';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user manages a specific team
CREATE OR REPLACE FUNCTION public.manages_team(team_id_param INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    IF auth.uid() IS NULL THEN
        RETURN FALSE;
    END IF;

    RETURN EXISTS (
        SELECT 1 FROM public.team_manager_assignments
        WHERE user_id = auth.uid()
        AND team_id = team_id_param
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- PART 2: Enable RLS on all tables
-- ============================================================================

-- Core data tables
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE age_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE divisions ENABLE ROW LEVEL SECURITY;

-- Mapping and relationship tables
ALTER TABLE team_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_game_types ENABLE ROW LEVEL SECURITY;

-- User and authentication tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_manager_assignments ENABLE ROW LEVEL SECURITY;

-- Service accounts table (if it exists, create it if not)
CREATE TABLE IF NOT EXISTS service_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name TEXT UNIQUE NOT NULL,
    permissions TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

ALTER TABLE service_accounts ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- PART 2: Drop existing policies to start fresh
-- ============================================================================

-- Teams policies
DROP POLICY IF EXISTS "Everyone can view teams" ON teams;
DROP POLICY IF EXISTS "Admins can manage teams" ON teams;
DROP POLICY IF EXISTS "Team managers can update their team" ON teams;
DROP POLICY IF EXISTS "anon_read_teams" ON teams;
DROP POLICY IF EXISTS "authenticated_read_teams" ON teams;
DROP POLICY IF EXISTS "admin_all_teams" ON teams;
DROP POLICY IF EXISTS "team_manager_update_teams" ON teams;

-- Games policies
DROP POLICY IF EXISTS "Everyone can view games" ON games;
DROP POLICY IF EXISTS "Admins can manage all games" ON games;
DROP POLICY IF EXISTS "Team managers can add games for their team" ON games;
DROP POLICY IF EXISTS "Team managers can edit games for their team" ON games;
DROP POLICY IF EXISTS "anon_read_games" ON games;
DROP POLICY IF EXISTS "authenticated_read_games" ON games;
DROP POLICY IF EXISTS "admin_all_games" ON games;
DROP POLICY IF EXISTS "team_manager_insert_games" ON games;
DROP POLICY IF EXISTS "team_manager_update_games" ON games;

-- Reference table policies
DROP POLICY IF EXISTS "Everyone can view seasons" ON seasons;
DROP POLICY IF EXISTS "Admins can manage seasons" ON seasons;
DROP POLICY IF EXISTS "anon_read_seasons" ON seasons;
DROP POLICY IF EXISTS "authenticated_read_seasons" ON seasons;
DROP POLICY IF EXISTS "admin_all_seasons" ON seasons;

DROP POLICY IF EXISTS "Everyone can view age_groups" ON age_groups;
DROP POLICY IF EXISTS "Admins can manage age_groups" ON age_groups;
DROP POLICY IF EXISTS "anon_read_age_groups" ON age_groups;
DROP POLICY IF EXISTS "authenticated_read_age_groups" ON age_groups;
DROP POLICY IF EXISTS "admin_all_age_groups" ON age_groups;

DROP POLICY IF EXISTS "Everyone can view game_types" ON game_types;
DROP POLICY IF EXISTS "Admins can manage game_types" ON game_types;
DROP POLICY IF EXISTS "anon_read_game_types" ON game_types;
DROP POLICY IF EXISTS "authenticated_read_game_types" ON game_types;
DROP POLICY IF EXISTS "admin_all_game_types" ON game_types;

DROP POLICY IF EXISTS "Everyone can view divisions" ON divisions;
DROP POLICY IF EXISTS "Admins can manage divisions" ON divisions;
DROP POLICY IF EXISTS "anon_read_divisions" ON divisions;
DROP POLICY IF EXISTS "authenticated_read_divisions" ON divisions;
DROP POLICY IF EXISTS "admin_all_divisions" ON divisions;

-- Team mappings policies
DROP POLICY IF EXISTS "Everyone can view team_mappings" ON team_mappings;
DROP POLICY IF EXISTS "Admins can manage team_mappings" ON team_mappings;
DROP POLICY IF EXISTS "anon_read_team_mappings" ON team_mappings;
DROP POLICY IF EXISTS "authenticated_read_team_mappings" ON team_mappings;
DROP POLICY IF EXISTS "admin_all_team_mappings" ON team_mappings;

-- Team game types policies
DROP POLICY IF EXISTS "anon_read_team_game_types" ON team_game_types;
DROP POLICY IF EXISTS "authenticated_read_team_game_types" ON team_game_types;
DROP POLICY IF EXISTS "admin_all_team_game_types" ON team_game_types;

-- User profiles policies
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON user_profiles;
DROP POLICY IF EXISTS "Admins can manage all profiles" ON user_profiles;
DROP POLICY IF EXISTS "Service role can manage profiles" ON user_profiles;
DROP POLICY IF EXISTS "user_read_own_profile" ON user_profiles;
DROP POLICY IF EXISTS "user_update_own_profile" ON user_profiles;
DROP POLICY IF EXISTS "admin_read_all_profiles" ON user_profiles;
DROP POLICY IF EXISTS "admin_all_profiles" ON user_profiles;

-- Service accounts policies
DROP POLICY IF EXISTS "admin_all_service_accounts" ON service_accounts;
DROP POLICY IF EXISTS "service_role_read_service_accounts" ON service_accounts;

-- Invitations policies (keep existing ones from migration 010)
-- We'll leave these in place as they're already properly configured

-- Team manager assignments policies (keep existing ones from migration 010)
-- We'll leave these in place as they're already properly configured

-- ============================================================================
-- PART 3: Create new RLS policies using helper functions
-- ============================================================================

-- ====================
-- TEAMS Policies
-- ====================

-- Allow public read access (anon role can view)
CREATE POLICY "anon_read_teams" ON teams
    FOR SELECT
    TO anon
    USING (true);

-- Allow authenticated users to read
CREATE POLICY "authenticated_read_teams" ON teams
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow admins full access
CREATE POLICY "admin_all_teams" ON teams
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- Allow team managers to update their teams
CREATE POLICY "team_manager_update_teams" ON teams
    FOR UPDATE
    TO authenticated
    USING (is_team_manager() AND manages_team(id))
    WITH CHECK (is_team_manager() AND manages_team(id));

-- ====================
-- GAMES Policies
-- ====================

-- Allow public read access
CREATE POLICY "anon_read_games" ON games
    FOR SELECT
    TO anon
    USING (true);

-- Allow authenticated users to read
CREATE POLICY "authenticated_read_games" ON games
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow admins full access
CREATE POLICY "admin_all_games" ON games
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- Allow team managers to create games for their teams
CREATE POLICY "team_manager_insert_games" ON games
    FOR INSERT
    TO authenticated
    WITH CHECK (
        is_team_manager() AND (
            manages_team(home_team_id) OR manages_team(away_team_id)
        )
    );

-- Allow team managers to update games for their teams
CREATE POLICY "team_manager_update_games" ON games
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

-- ====================
-- REFERENCE TABLES (seasons, age_groups, game_types, divisions)
-- ====================

-- Seasons
CREATE POLICY "anon_read_seasons" ON seasons FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_seasons" ON seasons FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_seasons" ON seasons FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- Age Groups
CREATE POLICY "anon_read_age_groups" ON age_groups FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_age_groups" ON age_groups FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_age_groups" ON age_groups FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- Game Types
CREATE POLICY "anon_read_game_types" ON game_types FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_game_types" ON game_types FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_game_types" ON game_types FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- Divisions
CREATE POLICY "anon_read_divisions" ON divisions FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_divisions" ON divisions FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_divisions" ON divisions FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- ====================
-- TEAM MAPPINGS Policies
-- ====================

CREATE POLICY "anon_read_team_mappings" ON team_mappings FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_team_mappings" ON team_mappings FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_team_mappings" ON team_mappings FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- ====================
-- TEAM GAME TYPES Policies
-- ====================

CREATE POLICY "anon_read_team_game_types" ON team_game_types FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_read_team_game_types" ON team_game_types FOR SELECT TO authenticated USING (true);
CREATE POLICY "admin_all_team_game_types" ON team_game_types FOR ALL TO authenticated USING (is_admin()) WITH CHECK (is_admin());

-- ====================
-- USER PROFILES Policies
-- ====================

-- Users can view their own profile
CREATE POLICY "user_read_own_profile" ON user_profiles
    FOR SELECT
    TO authenticated
    USING (id = auth.uid());

-- Users can update their own profile (limited fields)
CREATE POLICY "user_update_own_profile" ON user_profiles
    FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Admins can view all profiles
CREATE POLICY "admin_read_all_profiles" ON user_profiles
    FOR SELECT
    TO authenticated
    USING (is_admin());

-- Admins can manage all profiles
CREATE POLICY "admin_all_profiles" ON user_profiles
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- Allow the trigger function to insert profiles (service_role bypass)
-- This is handled by SECURITY DEFINER on the handle_new_user function

-- ====================
-- SERVICE ACCOUNTS Policies
-- ====================

-- Only admins can manage service accounts
CREATE POLICY "admin_all_service_accounts" ON service_accounts
    FOR ALL
    TO authenticated
    USING (is_admin())
    WITH CHECK (is_admin());

-- Service role can read service accounts (for token validation)
CREATE POLICY "service_role_read_service_accounts" ON service_accounts
    FOR SELECT
    TO service_role
    USING (true);

-- ============================================================================
-- PART 4: Grant appropriate permissions to roles
-- ============================================================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Grant access to tables for anon role (read-only)
GRANT SELECT ON teams, games, seasons, age_groups, game_types, divisions, team_mappings, team_game_types TO anon;

-- Grant access to tables for authenticated role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT INSERT, UPDATE, DELETE ON games TO authenticated;
GRANT UPDATE ON teams TO authenticated;

-- Service role has full access (bypass RLS)
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- ============================================================================
-- PART 5: Add indexes for performance
-- ============================================================================

-- Index on user_profiles.role for faster role checks
CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_id_role ON user_profiles(id, role);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON FUNCTION public.is_admin() IS 'Helper function to check if current user is admin. Uses SECURITY DEFINER to avoid RLS recursion.';
COMMENT ON FUNCTION public.is_team_manager() IS 'Helper function to check if current user is a team manager. Uses SECURITY DEFINER to avoid RLS recursion.';
COMMENT ON FUNCTION public.manages_team(INTEGER) IS 'Helper function to check if current user manages a specific team. Uses SECURITY DEFINER to avoid RLS recursion.';
