-- Divisions with no matches this season, for the scraper agent (SB-1080)
--
-- The agent's targets come from matches MT already has, so a division holding
-- none is invisible to it (SB-839); get_bootstrap_divisions offers those
-- divisions as first loads. It found them by fetching the division_id of every
-- non-cancelled match in the season and building the set in Python — 5,331
-- rows in six PostgREST round trips for 2026-2027, growing with every fixture —
-- to answer a question whose answer is about twenty divisions.
--
-- That is the shape SB-1057 removed from the same endpoint: the agent runs
-- hours apart, so it is always the cold caller, and work that scales with the
-- season is what trips Supabase's gateway timeout. This is one NOT EXISTS probe
-- per division on idx_matches_division_id instead.
--
-- Rules, unchanged from the Python this replaces:
--   - a league that is not active is retired, not unseeded. is_active is
--     nullable, and NULL was falsy in Python, hence IS TRUE
--   - test leagues only with p_include_test
--   - any match not cancelled seeds its division, test fixture or not. A match
--     with a NULL status does not: PostgREST's neq excluded NULLs, as <> does
--   - ordered by league, then division, by code point (COLLATE "C"), which is
--     the order Python's sorted() produced
--
-- It reads matches rather than matches_with_test: that view adds only the
-- derived is_test column, which this does not use.
--
-- An unknown season id has no matches, so every active division qualifies. The
-- DAO resolves the season name first and returns [] for one it does not know.

CREATE OR REPLACE FUNCTION public.agent_bootstrap_divisions(
    p_season_id integer,
    p_include_test boolean DEFAULT false
)
RETURNS TABLE (
    division_id integer,
    division text,
    league text
)
LANGUAGE sql
STABLE
AS $$
    SELECT d.id, d.name::text, l.name::text
    FROM public.divisions d
    JOIN public.leagues l ON l.id = d.league_id
    WHERE l.is_active IS TRUE
      AND (p_include_test OR NOT l.is_test)
      AND NOT EXISTS (
          SELECT 1
          FROM public.matches m
          WHERE m.division_id = d.id
            AND m.season_id = p_season_id
            AND m.match_status <> 'cancelled'
      )
    ORDER BY l.name COLLATE "C", d.name COLLATE "C";
$$;

COMMENT ON FUNCTION public.agent_bootstrap_divisions IS
    'Active divisions with no non-cancelled match in the season: first loads for '
    'the scraper agent. Replaces a scan of every match in the season (SB-1080).';

-- Matches agent_match_summary: the DAO falls back to the anon key when
-- SUPABASE_SERVICE_KEY is absent, and the endpoint's own permission dependency
-- is the real gate.
GRANT EXECUTE ON FUNCTION public.agent_bootstrap_divisions(integer, boolean)
    TO anon, authenticated, service_role;
