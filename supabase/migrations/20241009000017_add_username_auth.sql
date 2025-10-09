-- Username Authentication Migration
-- Add username-based authentication support while maintaining Supabase Auth infrastructure
-- Part of feature/username-auth-refactor

-- ============================================================================
-- PART 1: Create or modify user_profiles table structure
-- ============================================================================

-- Create user_profiles table if it doesn't exist
-- This table stores user profile information beyond Supabase Auth
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    display_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'team-fan' CHECK (role IN ('admin', 'team-manager', 'team-player', 'team-fan')),
    team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add username column (nullable initially for existing users)
-- Username will be the primary login identifier (e.g., gabe_ifa_35)
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS username VARCHAR(50);

-- Add unique constraint on username
ALTER TABLE public.user_profiles
ADD CONSTRAINT user_profiles_username_unique UNIQUE (username);

-- Create index for fast username lookups during login
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_username
ON public.user_profiles(username);

-- Make email nullable (was previously required via Supabase Auth)
-- Email becomes optional for username-only accounts
ALTER TABLE public.user_profiles
ALTER COLUMN email DROP NOT NULL;

-- Add phone number for future SMS notifications (optional)
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);

-- ============================================================================
-- PART 2: Add timestamp management
-- ============================================================================

-- Add created_at if not exists
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Add updated_at if not exists
ALTER TABLE public.user_profiles
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS user_profiles_updated_at_trigger ON public.user_profiles;
CREATE TRIGGER user_profiles_updated_at_trigger
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- ============================================================================
-- PART 3: Add documentation comments
-- ============================================================================

COMMENT ON COLUMN public.user_profiles.username IS 'Unique username for login (e.g., gabe_ifa_35). Replaces email as primary login credential.';
COMMENT ON COLUMN public.user_profiles.email IS 'Optional email for notifications (parent email). No longer required for authentication.';
COMMENT ON COLUMN public.user_profiles.phone_number IS 'Optional phone number for SMS notifications (future feature).';

-- ============================================================================
-- PART 4: Create helper function for internal email conversion
-- ============================================================================

-- Function to check if email is internal format (username@missingtable.local)
CREATE OR REPLACE FUNCTION is_internal_email(email_address TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN email_address LIKE '%@missingtable.local';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION is_internal_email(TEXT) IS 'Check if email is internal format used for username authentication';

-- ============================================================================
-- PART 5: Validation and constraints
-- ============================================================================

-- Add check constraint for username format (3-50 chars, alphanumeric and underscore only)
ALTER TABLE public.user_profiles
ADD CONSTRAINT username_format_check
CHECK (username IS NULL OR (username ~ '^[a-zA-Z0-9_]{3,50}$'));

-- Add check constraint for phone number format (basic validation)
ALTER TABLE public.user_profiles
ADD CONSTRAINT phone_number_format_check
CHECK (phone_number IS NULL OR (phone_number ~ '^\+?[0-9\s\-\(\)]{7,20}$'));

-- ============================================================================
-- PART 6: Migration notes
-- ============================================================================

-- Migration Strategy:
-- 1. Existing users: username will be NULL initially
-- 2. Run migrate_email_to_username.py script to populate usernames
-- 3. After all users migrated, can optionally make username NOT NULL
-- 4. Internal emails in auth.users: username@missingtable.local
-- 5. Real emails stored separately in user_profiles.email

-- Example data after migration:
-- auth.users.email: 'gabe_ifa_35@missingtable.local' (internal, not visible to users)
-- user_profiles.username: 'gabe_ifa_35' (primary login credential)
-- user_profiles.email: 'dad@example.com' (optional, for notifications)

-- ============================================================================
-- PART 7: Verify migration
-- ============================================================================

-- Check that migration completed successfully
DO $$
BEGIN
    -- Verify username column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'username'
    ) THEN
        RAISE EXCEPTION 'Migration failed: username column not created';
    END IF;

    -- Verify index exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = 'user_profiles'
        AND indexname = 'idx_user_profiles_username'
    ) THEN
        RAISE EXCEPTION 'Migration failed: username index not created';
    END IF;

    RAISE NOTICE 'Username authentication migration completed successfully!';
END $$;
