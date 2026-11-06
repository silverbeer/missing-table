-- SB-1559: Tournament Match of the Day.
--
-- The tournament sibling of match_of_the_week (SB-1010). A tournament like
-- MLS NEXT Fest runs for days with dozens of matches each day, so the
-- editorial unit is (tournament, day), not the calendar week.
--
-- Deliberately a separate table rather than a generalised match_of_the_week:
-- MOTW's UNIQUE(week_start) and its pick ordinal ("Week 6") are global by
-- design, and loosening them to admit tournament rows would put that
-- behaviour at risk for no gain.
--
-- The "one per day" rule lives in UNIQUE(tournament_id, match_date) for the
-- same reason MOTW's does: two admin tabs beat any check-then-insert.
-- match_date is the featured match's own date, copied here so the constraint
-- can see it; the API rejects a match that is not in the tournament or not on
-- that date.

CREATE TABLE IF NOT EXISTS public.tournament_match_of_the_day (
    id serial PRIMARY KEY,
    tournament_id integer NOT NULL REFERENCES public.tournaments(id) ON DELETE CASCADE,
    match_date date NOT NULL,
    match_id integer NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    blurb text,
    reasons jsonb,
    selected_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT motd_one_per_tournament_day UNIQUE (tournament_id, match_date)
);

COMMENT ON TABLE public.tournament_match_of_the_day IS
    'SB-1559: one admin-selected featured match per tournament per day.';

COMMENT ON COLUMN public.tournament_match_of_the_day.match_date IS
    'The featured match''s date. With tournament_id, UNIQUE -- this pair is what makes the pick singular.';

COMMENT ON COLUMN public.tournament_match_of_the_day.blurb IS
    'Optional one-line headline. NULL means none was written, which is not the same as an empty one.';

COMMENT ON COLUMN public.tournament_match_of_the_day.reasons IS
    '"Why this is the Match of the Day": JSON array of {text, kind}. NULL = never provided; [] = provided, empty.';

COMMENT ON COLUMN public.tournament_match_of_the_day.selected_by IS
    'Admin (or agent account) who made the pick. Not a FK to auth.users, matching match_of_the_week: a deleted admin must not cascade away the editorial history.';

CREATE INDEX IF NOT EXISTS idx_motd_match_id ON public.tournament_match_of_the_day (match_id);

ALTER TABLE public.tournament_match_of_the_day ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view tournament match of the day" ON public.tournament_match_of_the_day;
CREATE POLICY "Anyone can view tournament match of the day"
    ON public.tournament_match_of_the_day FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Admins can manage tournament match of the day" ON public.tournament_match_of_the_day;
CREATE POLICY "Admins can manage tournament match of the day"
    ON public.tournament_match_of_the_day TO authenticated
    USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Service role can manage tournament match of the day" ON public.tournament_match_of_the_day;
CREATE POLICY "Service role can manage tournament match of the day"
    ON public.tournament_match_of_the_day TO service_role
    USING (true) WITH CHECK (true);

GRANT SELECT ON public.tournament_match_of_the_day TO anon, authenticated;
GRANT ALL ON public.tournament_match_of_the_day TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.tournament_match_of_the_day_id_seq TO service_role;
