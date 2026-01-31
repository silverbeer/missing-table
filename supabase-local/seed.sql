-- =============================================================================
-- Seed data: Reference tables required for the application to function
-- =============================================================================
-- This runs automatically after migrations during `npx supabase db reset`
-- These are the core lookup/reference tables that the app depends on.
-- =============================================================================

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
INSERT INTO public.seasons (id, name, start_date, end_date) VALUES
  (1, '2023-2024', '2023-09-01', '2024-06-30'),
  (2, '2024-2025', '2024-09-01', '2025-06-30'),
  (3, '2025-2026', '2025-09-01', '2026-06-30')
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.seasons_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.seasons));

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
  (7, 'New England', 'New England Division', 2)
ON CONFLICT (id) DO NOTHING;

SELECT setval('public.divisions_id_seq', (SELECT COALESCE(MAX(id), 0) FROM public.divisions));
