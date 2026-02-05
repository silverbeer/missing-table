-- Allow free-form bracket tier names instead of constraining to 'upper'/'lower'.
-- This enables admins to name tiers like "Gold", "Silver", "Bronze" etc.

-- Remove the CHECK constraint that restricts to 'upper'/'lower'
ALTER TABLE public.playoff_bracket_slots
    DROP CONSTRAINT IF EXISTS playoff_bracket_slots_bracket_tier_check;

-- bracket_tier is now a free-form string (e.g., "Gold", "Silver", "Bronze")
-- No CHECK constraint needed - any non-empty string is valid
