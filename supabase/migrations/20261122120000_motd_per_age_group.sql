-- SB-1750: Tournament Match of the Day per age group.
--
-- SB-1559 kept one pick per tournament per day. MLS NEXT Fest plays six age
-- groups at once, so the product now picks one per age group each day. A
-- pick's slot is (tournament_id, match_date, age_group_id), and the UNIQUE
-- constraint moves from the pair to that triple. Re-picking a slot is still
-- an upsert.
--
-- Existing rows are filled in from their match: the age group is the match's.
-- A single-age tournament keeps exactly the picks it had.
--
-- Apply this right before deploying the SB-1750 backend: the old backend
-- upserts on (tournament_id, match_date), which no longer has a constraint to
-- match, and the new one writes a column that does not exist until this runs.
-- Public reads work on either side of the gap.

ALTER TABLE public.tournament_match_of_the_day
    ADD COLUMN IF NOT EXISTS age_group_id integer REFERENCES public.age_groups(id);

UPDATE public.tournament_match_of_the_day AS d
SET age_group_id = m.age_group_id
FROM public.matches AS m
WHERE m.id = d.match_id
  AND d.age_group_id IS NULL;

ALTER TABLE public.tournament_match_of_the_day
    ALTER COLUMN age_group_id SET NOT NULL;

ALTER TABLE public.tournament_match_of_the_day
    DROP CONSTRAINT IF EXISTS motd_one_per_tournament_day;
ALTER TABLE public.tournament_match_of_the_day
    DROP CONSTRAINT IF EXISTS motd_one_per_slot;
ALTER TABLE public.tournament_match_of_the_day
    ADD CONSTRAINT motd_one_per_slot UNIQUE (tournament_id, match_date, age_group_id);

COMMENT ON TABLE public.tournament_match_of_the_day IS
    'SB-1559, SB-1750: one admin-selected featured match per tournament per day for each age group.';

COMMENT ON COLUMN public.tournament_match_of_the_day.match_date IS
    'The featured match''s date. With tournament_id and age_group_id, the UNIQUE slot key.';

COMMENT ON COLUMN public.tournament_match_of_the_day.age_group_id IS
    'Age group of the picked match; part of the slot key.';
