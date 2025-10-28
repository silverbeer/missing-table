-- Migration: Fix Function Search Path Security Vulnerability
-- Description: Adds explicit search_path to all SECURITY DEFINER functions
-- This prevents schema injection attacks where malicious schemas could override function behavior
-- Reference: https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable

-- ============================================================================
-- PART 1: RLS Security Functions (from migration 011)
-- ============================================================================

-- Function to check if current user is admin
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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

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
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- ============================================================================
-- PART 2: User Management Functions (from migration 004)
-- ============================================================================

-- Function to automatically create user profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, role, display_name)
    VALUES (
        NEW.id,
        'team-fan', -- Default role
        COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email)
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- Function to get current user's role
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
BEGIN
    RETURN (
        SELECT role FROM user_profiles
        WHERE id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- Function to check if user has role
CREATE OR REPLACE FUNCTION public.user_has_role(required_role TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid() AND role = required_role
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- Create admin user function (for initial setup)
CREATE OR REPLACE FUNCTION public.promote_to_admin(user_email TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    user_id UUID;
BEGIN
    -- Get user ID from email
    SELECT id INTO user_id
    FROM auth.users
    WHERE email = user_email;

    IF user_id IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Update role to admin
    UPDATE user_profiles
    SET role = 'admin', updated_at = NOW()
    WHERE id = user_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

-- ============================================================================
-- PART 3: Invitation System Functions (from migration 010)
-- ============================================================================

-- Update function for updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = public, pg_temp;

-- Function to generate unique invite codes
CREATE OR REPLACE FUNCTION public.generate_invite_code()
RETURNS VARCHAR(12) AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result VARCHAR(12) := '';
    i INTEGER;
    max_attempts INTEGER := 100;
    attempt INTEGER := 0;
BEGIN
    -- Try to generate a unique code
    WHILE attempt < max_attempts LOOP
        result := '';
        -- Generate 12 character code
        FOR i IN 1..12 LOOP
            result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
        END LOOP;

        -- Check if code already exists
        IF NOT EXISTS (SELECT 1 FROM public.invitations WHERE invite_code = result) THEN
            RETURN result;
        END IF;

        attempt := attempt + 1;
    END LOOP;

    -- If we couldn't generate a unique code, raise an error
    RAISE EXCEPTION 'Could not generate unique invite code after % attempts', max_attempts;
END;
$$ LANGUAGE plpgsql SET search_path = public, pg_temp;

-- Function to expire old invitations (can be run periodically)
CREATE OR REPLACE FUNCTION public.expire_old_invitations()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE public.invitations
    SET status = 'expired'
    WHERE status = 'pending'
    AND expires_at < NOW();

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql SET search_path = public, pg_temp;

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON FUNCTION public.is_admin() IS 'Security: Checks if current user is admin. Uses SECURITY DEFINER with fixed search_path to prevent schema injection attacks.';
COMMENT ON FUNCTION public.is_team_manager() IS 'Security: Checks if current user is a team manager. Uses SECURITY DEFINER with fixed search_path to prevent schema injection attacks.';
COMMENT ON FUNCTION public.manages_team(INTEGER) IS 'Security: Checks if current user manages a specific team. Uses SECURITY DEFINER with fixed search_path to prevent schema injection attacks.';
COMMENT ON FUNCTION public.handle_new_user() IS 'Security: Trigger function to create user profile on signup. Uses SECURITY DEFINER with fixed search_path.';
COMMENT ON FUNCTION public.get_user_role() IS 'Security: Gets current user role. Uses SECURITY DEFINER with fixed search_path.';
COMMENT ON FUNCTION public.user_has_role(TEXT) IS 'Security: Checks if user has specific role. Uses SECURITY DEFINER with fixed search_path.';
COMMENT ON FUNCTION public.promote_to_admin(TEXT) IS 'Security: Promotes user to admin by email. Uses SECURITY DEFINER with fixed search_path.';
COMMENT ON FUNCTION public.update_updated_at_column() IS 'Utility: Trigger function to update updated_at timestamp. Uses fixed search_path for consistency.';
COMMENT ON FUNCTION public.generate_invite_code() IS 'Utility: Generates unique 12-character invitation codes. Uses fixed search_path for consistency.';
COMMENT ON FUNCTION public.expire_old_invitations() IS 'Utility: Expires old pending invitations. Uses fixed search_path for consistency.';
