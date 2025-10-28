-- Add Username Authentication Columns to Existing user_profiles Table
-- This migration adds email, username, and phone_number columns

-- ============================================================================
-- STEP 1: Add email column (nullable)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'email'
    ) THEN
        ALTER TABLE public.user_profiles ADD COLUMN email VARCHAR(255);
        RAISE NOTICE 'Added email column';
    ELSE
        RAISE NOTICE 'Email column already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Add username column
-- ============================================================================

DO $$
BEGIN
    -- Drop existing constraints/indexes if they exist
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_profiles_username_unique') THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT user_profiles_username_unique;
    END IF;

    -- Drop index if exists
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_profiles_username') THEN
        DROP INDEX public.idx_user_profiles_username;
    END IF;

    -- Drop column if exists (for clean slate)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'username'
    ) THEN
        ALTER TABLE public.user_profiles DROP COLUMN username;
        RAISE NOTICE 'Dropped existing username column';
    END IF;

    -- Add username column
    ALTER TABLE public.user_profiles ADD COLUMN username VARCHAR(50);
    RAISE NOTICE 'Added username column';

    -- Add unique constraint
    ALTER TABLE public.user_profiles ADD CONSTRAINT user_profiles_username_unique UNIQUE (username);
    RAISE NOTICE 'Added username unique constraint';

    -- Create index
    CREATE UNIQUE INDEX idx_user_profiles_username ON public.user_profiles(username);
    RAISE NOTICE 'Created username index';
END $$;

-- ============================================================================
-- STEP 3: Add phone_number column
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'phone_number'
    ) THEN
        ALTER TABLE public.user_profiles ADD COLUMN phone_number VARCHAR(20);
        RAISE NOTICE 'Added phone_number column';
    ELSE
        RAISE NOTICE 'Phone_number column already exists';
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Add validation constraints
-- ============================================================================

DO $$
BEGIN
    -- Drop existing constraints if they exist
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'username_format_check') THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT username_format_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'phone_number_format_check') THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT phone_number_format_check;
    END IF;

    -- Add validation constraints
    ALTER TABLE public.user_profiles
    ADD CONSTRAINT username_format_check
    CHECK (username IS NULL OR (username ~ '^[a-zA-Z0-9_]{3,50}$'));

    ALTER TABLE public.user_profiles
    ADD CONSTRAINT phone_number_format_check
    CHECK (phone_number IS NULL OR (phone_number ~ '^\+?[0-9\s\-\(\)]{7,20}$'));

    RAISE NOTICE 'Added validation constraints';
END $$;

-- ============================================================================
-- STEP 5: Update trigger function (already exists, ensure it's updated)
-- ============================================================================

CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Ensure trigger exists
DO $$
BEGIN
    DROP TRIGGER IF EXISTS user_profiles_updated_at_trigger ON public.user_profiles;
    CREATE TRIGGER user_profiles_updated_at_trigger
        BEFORE UPDATE ON public.user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION update_user_profiles_updated_at();
    RAISE NOTICE 'Ensured updated_at trigger exists';
END $$;

-- ============================================================================
-- STEP 6: Add helper function
-- ============================================================================

CREATE OR REPLACE FUNCTION is_internal_email(email_address TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN email_address LIKE '%@missingtable.local';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- STEP 7: Add comments
-- ============================================================================

COMMENT ON COLUMN public.user_profiles.username IS 'Unique username for login (e.g., tom). Replaces email as primary login credential.';
COMMENT ON COLUMN public.user_profiles.email IS 'Optional email for notifications. No longer required for authentication.';
COMMENT ON COLUMN public.user_profiles.phone_number IS 'Optional phone number for SMS notifications (future feature).';

-- ============================================================================
-- STEP 8: Verify migration
-- ============================================================================

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

    -- Verify email column exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'email'
    ) THEN
        RAISE EXCEPTION 'Migration failed: email column not created';
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
