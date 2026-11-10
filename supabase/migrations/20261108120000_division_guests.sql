-- SB-1598: teams that play in a table's fixtures without being members of it.
--
-- A Flex table is built from match participants, so a Pro Academy side that
-- plays a conference's teams gets a row. The official tables give it none, yet
-- still count those results for its opponents: U15 New England Flex has no
-- CF Montreal row, and every other team's line includes its CF Montreal match.
--
-- Neither existing lever can express that. team_mappings does not decide who
-- gets a row, and ingest writes it anyway (SB-852). Deleting or re-filing the
-- matches takes the opponents' results with them.
--
-- A row here hides the team from one table only. Per season because conference
-- membership is decided season by season.

CREATE TABLE IF NOT EXISTS public.division_guests (
    id serial PRIMARY KEY,
    team_id integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    division_id integer NOT NULL REFERENCES public.divisions(id) ON DELETE CASCADE,
    age_group_id integer NOT NULL REFERENCES public.age_groups(id) ON DELETE CASCADE,
    season_id integer NOT NULL REFERENCES public.seasons(id) ON DELETE CASCADE,
    reason text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT division_guests_one_per_table UNIQUE (team_id, division_id, age_group_id, season_id)
);

COMMENT ON TABLE public.division_guests IS
    'SB-1598: teams that get no row in a division''s table for an age group and season. Their matches still count for their opponents.';

COMMENT ON COLUMN public.division_guests.created_by IS
    'Admin who added the row. Not a FK to auth.users, matching match_of_the_week: a deleted admin must not cascade away a table''s membership.';

CREATE INDEX IF NOT EXISTS idx_division_guests_table
    ON public.division_guests (division_id, age_group_id, season_id);

ALTER TABLE public.division_guests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view division guests" ON public.division_guests;
CREATE POLICY "Anyone can view division guests"
    ON public.division_guests FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Admins can manage division guests" ON public.division_guests;
CREATE POLICY "Admins can manage division guests"
    ON public.division_guests TO authenticated
    USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Service role can manage division guests" ON public.division_guests;
CREATE POLICY "Service role can manage division guests"
    ON public.division_guests TO service_role
    USING (true) WITH CHECK (true);

GRANT SELECT ON public.division_guests TO anon, authenticated;
GRANT ALL ON public.division_guests TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.division_guests_id_seq TO service_role;
