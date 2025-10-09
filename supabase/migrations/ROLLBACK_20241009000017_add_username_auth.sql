-- Rollback Migration for Username Authentication
-- Use this to reverse changes if issues arise
-- Part of feature/username-auth-refactor

-- ⚠️  WARNING: This rollback will:
-- 1. Remove username column and all username data
-- 2. Remove phone_number column
-- 3. Remove related constraints and indexes
-- 4. Attempt to restore email as required field (may fail if NULL emails exist)
--
-- IMPORTANT: Backup database before running rollback!
-- Run: ./scripts/db_tools.sh backup

-- ============================================================================
-- PART 1: Remove constraints and indexes
-- ============================================================================

-- Drop username index
DROP INDEX IF EXISTS public.idx_user_profiles_username;

-- Drop username format check constraint
ALTER TABLE public.user_profiles
DROP CONSTRAINT IF EXISTS username_format_check;

-- Drop phone number format check constraint
ALTER TABLE public.user_profiles
DROP CONSTRAINT IF EXISTS phone_number_format_check;

-- Drop unique constraint on username
ALTER TABLE public.user_profiles
DROP CONSTRAINT IF EXISTS user_profiles_username_unique;

-- ============================================================================
-- PART 2: Remove trigger and function
-- ============================================================================

-- Drop updated_at trigger
DROP TRIGGER IF EXISTS user_profiles_updated_at_trigger ON public.user_profiles;

-- Drop updated_at function
DROP FUNCTION IF EXISTS update_user_profiles_updated_at();

-- Drop internal email check function
DROP FUNCTION IF EXISTS is_internal_email(TEXT);

-- ============================================================================
-- PART 3: Remove columns
-- ============================================================================

-- Remove phone number column
ALTER TABLE public.user_profiles
DROP COLUMN IF EXISTS phone_number;

-- Remove username column
-- WARNING: This will delete all username data!
ALTER TABLE public.user_profiles
DROP COLUMN IF EXISTS username;

-- Remove timestamp columns (optional - comment out if you want to keep these)
-- ALTER TABLE public.user_profiles
-- DROP COLUMN IF EXISTS created_at;
--
-- ALTER TABLE public.user_profiles
-- DROP COLUMN IF EXISTS updated_at;

-- ============================================================================
-- PART 4: Restore email as required (DANGEROUS)
-- ============================================================================

-- WARNING: This will FAIL if any users have NULL emails
-- Only uncomment if you're certain all users have email addresses

-- ALTER TABLE public.user_profiles
-- ALTER COLUMN email SET NOT NULL;

-- ============================================================================
-- PART 5: Verify rollback
-- ============================================================================

DO $$
BEGIN
    -- Verify username column removed
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'user_profiles'
        AND column_name = 'username'
    ) THEN
        RAISE EXCEPTION 'Rollback failed: username column still exists';
    END IF;

    -- Verify index removed
    IF EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = 'user_profiles'
        AND indexname = 'idx_user_profiles_username'
    ) THEN
        RAISE EXCEPTION 'Rollback failed: username index still exists';
    END IF;

    RAISE NOTICE 'Username authentication rollback completed successfully!';
    RAISE NOTICE 'NOTE: You may need to restore data from backup if user data was lost.';
END $$;

-- ============================================================================
-- PART 6: Post-Rollback Actions
-- ============================================================================

-- After running this rollback, you should:
-- 1. Restore user data from backup if needed
-- 2. Verify all users can login with email again
-- 3. Redeploy previous version of backend/frontend code
-- 4. Delete internal emails from auth.users if they exist
--    (emails ending in @missingtable.local)
