-- SB-1010: Match of the Week.
--
-- One editorial pick per week, global across every age group and division.
-- That scarcity is the whole product idea: a badge handed out six times a
-- week -- once per age group -- is a label, not an event.
--
-- The rule lives in a UNIQUE constraint on week_start rather than in
-- application etiquette, because "only one" enforced by convention lasts
-- exactly until two admin tabs are open. week_start is the Monday of the
-- match's week, computed by the caller from match_date.
--
-- Re-picking inside a week is an upsert on that key. Past weeks stay as
-- rows, so the archive -- and an eventual "MOTW of the season" retrospective
-- -- comes free rather than needing a second table later.

CREATE TABLE IF NOT EXISTS public.match_of_the_week (
    id serial PRIMARY KEY,
    match_id integer NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    week_start date NOT NULL,
    blurb text,
    selected_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT motw_one_per_week UNIQUE (week_start)
);

COMMENT ON TABLE public.match_of_the_week IS
    'SB-1010: one admin-selected featured match per calendar week, global across age groups.';

COMMENT ON COLUMN public.match_of_the_week.week_start IS
    'Monday of the week the match falls in. UNIQUE -- this column is what makes the pick singular.';

COMMENT ON COLUMN public.match_of_the_week.blurb IS
    'Optional editorial line shown on the hero card. NULL means no blurb was written, which is not the same as an empty one.';

COMMENT ON COLUMN public.match_of_the_week.selected_by IS
    'Admin who made the pick (CLAUDE.md: provenance is queryable). Deliberately not a FK to auth.users -- a deleted admin must not cascade away the editorial history.';

-- ON DELETE CASCADE above is the deliberate half: if the match itself is
-- deleted, a featured pick pointing at nothing is worse than no pick.

CREATE INDEX IF NOT EXISTS idx_motw_match_id ON public.match_of_the_week (match_id);

ALTER TABLE public.match_of_the_week ENABLE ROW LEVEL SECURITY;

-- Read is public: the hero card is the point, and most viewers are logged out.
DROP POLICY IF EXISTS "Anyone can view match of the week" ON public.match_of_the_week;
CREATE POLICY "Anyone can view match of the week"
    ON public.match_of_the_week FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Admins can manage match of the week" ON public.match_of_the_week;
CREATE POLICY "Admins can manage match of the week"
    ON public.match_of_the_week TO authenticated
    USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Service role can manage match of the week" ON public.match_of_the_week;
CREATE POLICY "Service role can manage match of the week"
    ON public.match_of_the_week TO service_role
    USING (true) WITH CHECK (true);

GRANT SELECT ON public.match_of_the_week TO anon, authenticated;
GRANT ALL ON public.match_of_the_week TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.match_of_the_week_id_seq TO service_role;
