-- Simple Username Authentication Migration for Cloud Dev
-- This version is more defensive and creates everything from scratch if needed

-- ============================================================================
-- STEP 1: Create user_profiles table if it doesn't exist
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255),
    display_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'team-fan' CHECK (role IN ('admin', 'team-manager', 'team-player', 'team-fan')),
    team_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- STEP 2: Add username column (with DROP/ADD to avoid conflicts)
-- ============================================================================

-- Drop constraint if it exists (from previous attempts)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'user_profiles_username_unique'
    ) THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT user_profiles_username_unique;
    END IF;
END $$;

-- Drop index if it exists
DROP INDEX IF EXISTS public.idx_user_profiles_username;

-- Drop column if it exists (clean slate)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'username'
    ) THEN
        ALTER TABLE public.user_profiles DROP COLUMN username;
    END IF;
END $$;

-- Now add username column fresh
ALTER TABLE public.user_profiles ADD COLUMN username VARCHAR(50);

-- Add unique constraint
ALTER TABLE public.user_profiles ADD CONSTRAINT user_profiles_username_unique UNIQUE (username);

-- Create index
CREATE UNIQUE INDEX idx_user_profiles_username ON public.user_profiles(username);

-- ============================================================================
-- STEP 3: Add phone number if not exists
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
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Make email nullable
-- ============================================================================

ALTER TABLE public.user_profiles ALTER COLUMN email DROP NOT NULL;

-- ============================================================================
-- STEP 5: Add timestamp management
-- ============================================================================

-- Ensure created_at exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE public.user_profiles ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;
END $$;

-- Ensure updated_at exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE public.user_profiles ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;
END $$;

-- Create or replace trigger function
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger
DROP TRIGGER IF EXISTS user_profiles_updated_at_trigger ON public.user_profiles;
CREATE TRIGGER user_profiles_updated_at_trigger
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- ============================================================================
-- STEP 6: Add validation constraints
-- ============================================================================

-- Drop existing constraints if they exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'username_format_check') THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT username_format_check;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'phone_number_format_check') THEN
        ALTER TABLE public.user_profiles DROP CONSTRAINT phone_number_format_check;
    END IF;
END $$;

-- Add validation constraints
ALTER TABLE public.user_profiles
ADD CONSTRAINT username_format_check
CHECK (username IS NULL OR (username ~ '^[a-zA-Z0-9_]{3,50}$'));

ALTER TABLE public.user_profiles
ADD CONSTRAINT phone_number_format_check
CHECK (phone_number IS NULL OR (phone_number ~ '^\+?[0-9\s\-\(\)]{7,20}$'));

-- ============================================================================
-- STEP 7: Add helper function
-- ============================================================================

CREATE OR REPLACE FUNCTION is_internal_email(email_address TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN email_address LIKE '%@missingtable.local';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

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
