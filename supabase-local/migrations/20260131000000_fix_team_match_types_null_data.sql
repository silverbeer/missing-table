-- =============================================================================
-- FIX: Remove team_match_types records with null required fields and
-- enforce NOT NULL constraints on match_type_id and age_group_id
-- =============================================================================
-- Problem: Prod schema was missing NOT NULL constraints on match_type_id and
-- age_group_id, allowing bad data (e.g., records 198, 199 for teams IFA West
-- and IFA Academy). Local schema had the constraints but prod drifted.
--
-- This migration:
--   1. Deletes any records with null match_type_id or age_group_id
--   2. Adds NOT NULL constraints to prevent future bad data
-- =============================================================================

-- Step 1: Clean up any null records
DELETE FROM public.team_match_types
WHERE match_type_id IS NULL OR age_group_id IS NULL;

-- Step 2: Enforce NOT NULL (idempotent - safe if constraints already exist)
ALTER TABLE public.team_match_types
    ALTER COLUMN match_type_id SET NOT NULL;

ALTER TABLE public.team_match_types
    ALTER COLUMN age_group_id SET NOT NULL;
