-- Add bracket_tier column to support dual-tier (upper/lower) playoff brackets.
-- Upper bracket: top 4 from each division. Lower bracket: positions 5-8.

ALTER TABLE public.playoff_bracket_slots
    ADD COLUMN bracket_tier VARCHAR(50);

-- Drop old unique constraint (round + position alone is no longer unique).
-- The auto-generated name varies by Postgres version, so look it up dynamically.
DO $$
DECLARE
    _constraint_name text;
BEGIN
    SELECT conname INTO _constraint_name
    FROM pg_constraint
    WHERE conrelid = 'public.playoff_bracket_slots'::regclass
      AND contype = 'u'
      AND conname LIKE 'playoff_bracket_slots_%key';

    IF _constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.playoff_bracket_slots DROP CONSTRAINT %I', _constraint_name);
    END IF;
END $$;

-- New unique constraint includes bracket_tier
ALTER TABLE public.playoff_bracket_slots
    ADD CONSTRAINT playoff_bracket_slots_unique_tier_round_position
    UNIQUE(league_id, season_id, age_group_id, bracket_tier, round, bracket_position);

-- Replace index to include bracket_tier
DROP INDEX IF EXISTS idx_playoff_bracket_league_season_ag;
CREATE INDEX idx_playoff_bracket_league_season_ag_tier
    ON public.playoff_bracket_slots(league_id, season_id, age_group_id, bracket_tier);
