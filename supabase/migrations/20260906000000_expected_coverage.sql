-- What MT is SUPPOSED to be tracking (SB-1021)
--
-- MT can already answer "which competitions are present" — get_competitions_present,
-- get_leagues_present, /api/match-types/available. Every one of those derives from
-- fixtures that arrived. None of them can tell you about a conference that arrived
-- nothing at all, because absence produces no row to count.
--
-- That is not hypothetical. On 2026-09-06, season 2026-2027 held fixtures for
-- 13 of 13 Flex conferences and 4 of 4 Pro Player Pathway divisions, but only
-- 2 of the 8 Homegrown League conferences — Northeast and Florida. Frontier,
-- Mid-America, Mid-Atlantic, Northwest, Southeast and Southwest had zero,
-- despite carrying 29-93 team_mappings rows each, and Mid-Atlantic having had
-- 200 fixtures in earlier seasons. `ingest_failures` has never held a single
-- row of kind 'division', so MT was not rejecting them — the feed never sent
-- them, and nothing in the product could say so.
--
-- This migration adds the missing half: a statement of what ought to arrive,
-- so the diff is a number somebody sees rather than something discovered by
-- accident months later.
--
-- Source: the official 2026-27 MLS NEXT competition structure decks
-- (Homegrown Division qualification pathway, Cup qualification, Flex
-- qualification). Age-group coverage below is read off those tables, not
-- inferred from what MT happens to hold.

-- === The eight Homegrown League conferences ================================
-- These exist in production but in NO migration and NO seed: supabase/seed.sql
-- creates only Northeast, Florida (Homegrown) and New England (Academy). A
-- fresh local or CI database therefore cannot represent six of the eight
-- conferences the real league runs, which is its own quiet source of "works on
-- prod, missing locally" confusion.
--
-- ON CONFLICT keeps production untouched — there the rows already exist.
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.description, l.id
FROM (VALUES
    ('Northeast',    'MLS NEXT Homegrown Division - Northeast Conference'),
    ('Mid-Atlantic', 'MLS NEXT Homegrown Division - Mid-Atlantic Conference'),
    ('Southeast',    'MLS NEXT Homegrown Division - Southeast Conference'),
    ('Florida',      'MLS NEXT Homegrown Division - Florida Conference'),
    ('Mid-America',  'MLS NEXT Homegrown Division - Mid-America Conference'),
    ('Frontier',     'MLS NEXT Homegrown Division - Frontier Conference'),
    ('Southwest',    'MLS NEXT Homegrown Division - Southwest Conference'),
    ('Northwest',    'MLS NEXT Homegrown Division - Northwest Conference')
) AS v(name, description)
CROSS JOIN public.leagues l
WHERE l.name = 'Homegrown'
ON CONFLICT (name, league_id) DO NOTHING;

-- === Expected coverage =====================================================
-- One row per (conference, age group, season) that the league actually runs.
-- Keyed on season because the structure changes year to year: Flex did not
-- exist before 2026-27, and the Homegrown Division expands from 32 to 48 teams
-- at U15-U19 for the 2027 Cup.
--
-- This is also where cup-berth data hangs when that work happens — spots per
-- conference per age, second-spot flags, bye eligibility — without needing
-- another table.
CREATE TABLE IF NOT EXISTS public.division_age_groups (
    id serial PRIMARY KEY,
    division_id integer NOT NULL REFERENCES public.divisions(id) ON DELETE CASCADE,
    age_group_id integer NOT NULL REFERENCES public.age_groups(id) ON DELETE CASCADE,
    season_id integer NOT NULL REFERENCES public.seasons(id) ON DELETE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT division_age_groups_unique UNIQUE (division_id, age_group_id, season_id)
);

COMMENT ON TABLE public.division_age_groups IS
    'SB-1021: the age groups each conference is expected to run in a season. The reference the coverage report diffs actual fixtures against.';

CREATE INDEX IF NOT EXISTS idx_division_age_groups_season
    ON public.division_age_groups (season_id);

ALTER TABLE public.division_age_groups ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view expected coverage" ON public.division_age_groups;
CREATE POLICY "Anyone can view expected coverage"
    ON public.division_age_groups FOR SELECT
    USING (true);

DROP POLICY IF EXISTS "Admins can manage expected coverage" ON public.division_age_groups;
CREATE POLICY "Admins can manage expected coverage"
    ON public.division_age_groups TO authenticated
    USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Service role can manage expected coverage" ON public.division_age_groups;
CREATE POLICY "Service role can manage expected coverage"
    ON public.division_age_groups TO service_role
    USING (true) WITH CHECK (true);

GRANT SELECT ON public.division_age_groups TO anon, authenticated;
GRANT ALL ON public.division_age_groups TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.division_age_groups_id_seq TO service_role;

-- === 2026-27 ===============================================================
-- Season and age groups are matched by name rather than id: ids differ between
-- local, CI and production, and a migration that hardcodes them silently seeds
-- the wrong season somewhere.

-- Homegrown League conferences run every age group, U13 through U19. Read off
-- the Cup qualification table, which lists spots for all eight conferences at
-- U13, U14, U15, U16, U17 and U19.
INSERT INTO public.division_age_groups (division_id, age_group_id, season_id)
SELECT d.id, ag.id, s.id
FROM public.divisions d
JOIN public.leagues l ON l.id = d.league_id AND l.name = 'Homegrown'
CROSS JOIN public.age_groups ag
CROSS JOIN public.seasons s
WHERE s.name = '2026-2027'
  AND d.name NOT LIKE '%(Pro Player Pathway)%'
  AND ag.name IN ('U13', 'U14', 'U15', 'U16', 'U17', 'U19')
ON CONFLICT ON CONSTRAINT division_age_groups_unique DO NOTHING;

-- Pro Player Pathway is U16/U17/U19 only. 29 of its 30 clubs field no U15 team
-- at all — that cohort plays up into U16 — which is why no U15 Pathway bracket
-- exists in any feed.
INSERT INTO public.division_age_groups (division_id, age_group_id, season_id)
SELECT d.id, ag.id, s.id
FROM public.divisions d
JOIN public.leagues l ON l.id = d.league_id AND l.name = 'Homegrown'
CROSS JOIN public.age_groups ag
CROSS JOIN public.seasons s
WHERE s.name = '2026-2027'
  AND d.name LIKE '%(Pro Player Pathway)%'
  AND ag.name IN ('U16', 'U17', 'U19')
ON CONFLICT ON CONSTRAINT division_age_groups_unique DO NOTHING;

-- Flex is U15-U19. There is no U13 or U14 Flex competition.
INSERT INTO public.division_age_groups (division_id, age_group_id, season_id)
SELECT d.id, ag.id, s.id
FROM public.divisions d
JOIN public.leagues l ON l.id = d.league_id AND l.name = 'Flex'
CROSS JOIN public.age_groups ag
CROSS JOIN public.seasons s
WHERE s.name = '2026-2027'
  AND ag.name IN ('U15', 'U16', 'U17', 'U19')
ON CONFLICT ON CONSTRAINT division_age_groups_unique DO NOTHING;

-- The Academy Division is deliberately NOT seeded here.
--
-- It is the second MLS NEXT tier and it is not a lesser one: since 2025-26 it
-- runs its own MLS NEXT Cup with separate U15, U16, U17 and U19 championship
-- finals, 32 teams per age group qualifying (16 through league play, 16 through
-- regional Cup Qualifiers), and it gains a play-in at MLS NEXT Fest for 2026-27.
--
-- MT currently holds one conference of it — New England — at U14 only. But the
-- decks this migration is sourced from describe the HOMEGROWN Division, so its
-- real conference map is not established here. Seeding a guess would produce a
-- coverage report that is confidently wrong, which is worse than one that says
-- it does not know. Until the real list is sourced, the report reports Academy
-- as unknown.

-- Academy's league description is stale: seed.sql calls it "MLS Next League 2",
-- which reads as a lower-stakes second competition rather than the second tier
-- of MLS NEXT with its own Cup.
UPDATE public.leagues
SET description = 'MLS NEXT Academy Division'
WHERE name = 'Academy'
  AND description = 'MLS Next League 2';
