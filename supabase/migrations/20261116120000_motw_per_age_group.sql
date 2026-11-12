-- SB-1638: Match of the Week per age group.
--
-- SB-1010 kept one pick per week, global. The product now picks one per age
-- group in each pool: the main pool (Homegrown Northeast League + Flex
-- Empire/Turnpike/New England, U15-U19) and the Pro Player Pathway (U16-U19).
-- A pick's slot is (week_start, pool, age_group_id), and the UNIQUE constraint
-- moves from week_start to that triple. Re-picking a slot is still an upsert.
--
-- Existing rows are filled in from their match: the age group is the match's,
-- and the pool is 'pathway' when the match is in a Pro Player Pathway division.
--
-- Apply this right before deploying the SB-1638 backend: the old backend
-- upserts on week_start alone, which no longer has a constraint to match.

ALTER TABLE public.match_of_the_week
    ADD COLUMN IF NOT EXISTS pool text NOT NULL DEFAULT 'main',
    ADD COLUMN IF NOT EXISTS age_group_id integer REFERENCES public.age_groups(id);

ALTER TABLE public.match_of_the_week
    DROP CONSTRAINT IF EXISTS motw_pool_known;
ALTER TABLE public.match_of_the_week
    ADD CONSTRAINT motw_pool_known CHECK (pool IN ('main', 'pathway'));

UPDATE public.match_of_the_week AS w
SET age_group_id = m.age_group_id,
    pool = CASE WHEN d.name ILIKE '%Pro Player Pathway%' THEN 'pathway' ELSE 'main' END
FROM public.matches AS m
LEFT JOIN public.divisions AS d ON d.id = m.division_id
WHERE m.id = w.match_id
  AND w.age_group_id IS NULL;

ALTER TABLE public.match_of_the_week
    ALTER COLUMN age_group_id SET NOT NULL;

ALTER TABLE public.match_of_the_week
    DROP CONSTRAINT IF EXISTS motw_one_per_week;
ALTER TABLE public.match_of_the_week
    DROP CONSTRAINT IF EXISTS motw_one_per_slot;
ALTER TABLE public.match_of_the_week
    ADD CONSTRAINT motw_one_per_slot UNIQUE (week_start, pool, age_group_id);

COMMENT ON TABLE public.match_of_the_week IS
    'SB-1010, SB-1638: one featured match per week for each (pool, age group) slot.';

COMMENT ON COLUMN public.match_of_the_week.week_start IS
    'Monday of the week the match falls in. With pool and age_group_id, the UNIQUE slot key.';

COMMENT ON COLUMN public.match_of_the_week.pool IS
    'Which MOTW pool the pick belongs to: main (Homegrown Northeast + Flex Empire/Turnpike/New England) or pathway (Northeast Pro Player Pathway).';

COMMENT ON COLUMN public.match_of_the_week.age_group_id IS
    'Age group of the picked match; part of the slot key.';
