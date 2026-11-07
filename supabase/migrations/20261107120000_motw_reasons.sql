-- SB-1552: "Why is this the Match of the Week?" reasons.
--
-- A list of {text, kind} objects, same shape as
-- tournament_match_of_the_day.reasons. NULL means never provided; '[]' means
-- provided and empty. The two are kept distinct on purpose (CLAUDE.md: never
-- collapse absent into empty).
--
-- match_of_the_week is already in the backup and restore lists; a new column
-- needs no registry change.

ALTER TABLE public.match_of_the_week
    ADD COLUMN IF NOT EXISTS reasons jsonb;

ALTER TABLE public.match_of_the_week
    DROP CONSTRAINT IF EXISTS motw_reasons_is_array;
ALTER TABLE public.match_of_the_week
    ADD CONSTRAINT motw_reasons_is_array
    CHECK (reasons IS NULL OR jsonb_typeof(reasons) = 'array');

COMMENT ON COLUMN public.match_of_the_week.reasons IS
    'Why this is the Match of the Week: [{text, kind}]. NULL = never provided, [] = provided empty (SB-1552).';
