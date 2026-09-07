-- =============================================================================
-- Seed data: Reference tables required for the application to function
-- =============================================================================
-- This runs automatically after migrations during `npx supabase db reset`
-- These are the core lookup/reference tables that the app depends on.
-- =============================================================================

-- The consolidated baseline schema leaves the Supabase API roles without
-- table grants on a fresh reset (everything then fails with 42501 permission
-- denied — auth lookups, restores, PostgREST). Re-grant here; seed always
-- runs after migrations during `db reset`.
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

-- Age Groups
INSERT INTO public.age_groups (id, name) VALUES
  (1, 'U13'),
  (2, 'U14'),
  (3, 'U15'),
  (4, 'U16'),
  (5, 'U17'),
  (7, 'U19')
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.age_groups_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.age_groups));

-- Seasons
-- Migration 20260709000000 (SB-260) inserts '2026-2027' by name; on a fresh DB
-- that runs before this seed and claims id 1, colliding with the explicit ids
-- below. Seed owns reference data on a fresh DB, so clear the table first
-- (nothing references seasons yet at seed time).
DELETE FROM public.seasons;
INSERT INTO public.seasons (id, name, start_date, end_date) VALUES
  (1, '2023-2024', '2023-09-01', '2024-06-30'),
  (2, '2024-2025', '2024-09-01', '2025-06-30'),
  (3, '2025-2026', '2025-09-01', '2026-06-30'),
  (4, '2026-2027', '2026-09-01', '2027-06-30')
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.seasons_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.seasons));

-- Exactly one season must be current. Plenty of code resolves "now" through
-- seasons.is_current rather than through dates -- the TSC world seed refuses to
-- run without it -- and a freshly reset database had none, so every such path
-- failed on a database that looked fully seeded (SB-918).
UPDATE public.seasons SET is_current = (name = '2026-2027');

-- Match Types
INSERT INTO public.match_types (id, name) VALUES
  (1, 'League'),
  (2, 'Tournament'),
  (3, 'Friendly'),
  (4, 'Playoff')
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.match_types_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.match_types));

-- Leagues
INSERT INTO public.leagues (id, name, description, is_active) VALUES
  (1, 'Homegrown', 'MLS Next Top League', true),
  (2, 'Academy', 'MLS Next League 2', true)
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.leagues_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.leagues));

-- Divisions (depend on leagues)
INSERT INTO public.divisions (id, name, description, league_id) VALUES
  (1, 'Northeast', 'Northeast Division', 1),
  (2, 'Florida', 'Florida Division', 1),
  (7, 'New England', 'New England Division', 2)
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.divisions_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.divisions));

-- Competition coverage reference data (SB-1021)
-- ---------------------------------------------------------------------------
-- The six Homegrown conferences beyond Northeast and Florida, plus the
-- statement of which age groups each conference runs. Production gets these
-- from the 20260906 migrations; seed carries them too because seed runs AFTER
-- migrations on a fresh reset, and `DELETE FROM public.seasons` above cascades
-- away any division_age_groups rows the migration created.
--
-- Everything below resolves by name and is idempotent, so it is a no-op in any
-- environment that already has the rows.
--
-- KNOWN LIMITATION: on a completely fresh `db reset` these inserts can seed
-- nothing, because reference data created by migrations into empty tables
-- claims the explicit ids this file expects (a Flex match type inserted at id
-- 1 makes the `(1, 'League')` insert above a no-op). That collision predates
-- this work and is tracked separately — every real environment is restored
-- from production, where the reference rows are correct.
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.description, l.id
FROM (VALUES
    ('Mid-Atlantic', 'MLS NEXT Homegrown Division - Mid-Atlantic Conference'),
    ('Southeast',    'MLS NEXT Homegrown Division - Southeast Conference'),
    ('Mid-America',  'MLS NEXT Homegrown Division - Mid-America Conference'),
    ('Frontier',     'MLS NEXT Homegrown Division - Frontier Conference'),
    ('Southwest',    'MLS NEXT Homegrown Division - Southwest Conference'),
    ('Northwest',    'MLS NEXT Homegrown Division - Northwest Conference')
) AS v(name, description)
CROSS JOIN public.leagues l
WHERE l.name = 'Homegrown'
ON CONFLICT (name, league_id) DO NOTHING;

-- The twenty Academy conferences (SB-1044). Production held one of them, so a
-- local database could not represent the league at all. Mid-Atlantic and
-- Northeast are also Homegrown conference names; they are different
-- competitions, kept apart by the (name, league_id) key.
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.description, l.id
FROM (VALUES
    ('Carolinas',                   'MLS NEXT Academy Division - Carolinas Conference'),
    ('Desert',                      'MLS NEXT Academy Division - Desert Conference'),
    ('Garden State',                'MLS NEXT Academy Division - Garden State Conference'),
    ('Great Lakes North',           'MLS NEXT Academy Division - Great Lakes North Conference'),
    ('Great Lakes South',           'MLS NEXT Academy Division - Great Lakes South Conference'),
    ('Heartland',                   'MLS NEXT Academy Division - Heartland Conference'),
    ('Mid-Atlantic',                'MLS NEXT Academy Division - Mid-Atlantic Conference'),
    ('Mountain',                    'MLS NEXT Academy Division - Mountain Conference'),
    ('New England',                 'MLS NEXT Academy Division - New England Conference'),
    ('North',                       'MLS NEXT Academy Division - North Conference'),
    ('Northeast',                   'MLS NEXT Academy Division - Northeast Conference'),
    ('Northern California Coast',   'MLS NEXT Academy Division - Northern California Coast Conference'),
    ('Northern California Redwood', 'MLS NEXT Academy Division - Northern California Redwood Conference'),
    ('Pacific Northwest',           'MLS NEXT Academy Division - Pacific Northwest Conference'),
    ('Pioneer',                     'MLS NEXT Academy Division - Pioneer Conference'),
    ('South',                       'MLS NEXT Academy Division - South Conference'),
    ('Southern California',         'MLS NEXT Academy Division - Southern California Conference'),
    ('Sunshine North',              'MLS NEXT Academy Division - Sunshine North Conference'),
    ('Sunshine South',              'MLS NEXT Academy Division - Sunshine South Conference'),
    ('Virginia',                    'MLS NEXT Academy Division - Virginia Conference')
) AS v(name, description)
CROSS JOIN public.leagues l
WHERE l.name = 'Academy'
ON CONFLICT (name, league_id) DO NOTHING;

-- Homegrown League conferences run U13-U19; Pro Player Pathway U16/U17/U19;
-- Flex U15-U19; Academy U13-U19 across all twenty conferences. Read off the
-- 2026-27 competition structure, not inferred from what MT happens to hold.
INSERT INTO public.division_age_groups (division_id, age_group_id, season_id)
SELECT d.id, ag.id, s.id
FROM public.divisions d
JOIN public.leagues l ON l.id = d.league_id
CROSS JOIN public.age_groups ag
CROSS JOIN public.seasons s
WHERE s.name = '2026-2027'
  AND (
        (l.name = 'Homegrown' AND d.name NOT LIKE '%(Pro Player Pathway)%'
            AND ag.name IN ('U13', 'U14', 'U15', 'U16', 'U17', 'U19'))
     OR (l.name = 'Homegrown' AND d.name LIKE '%(Pro Player Pathway)%'
            AND ag.name IN ('U16', 'U17', 'U19'))
     OR (l.name = 'Flex' AND ag.name IN ('U15', 'U16', 'U17', 'U19'))
     OR (l.name = 'Academy'
            AND ag.name IN ('U13', 'U14', 'U15', 'U16', 'U17', 'U19'))
  )
ON CONFLICT ON CONSTRAINT division_age_groups_unique DO NOTHING;
