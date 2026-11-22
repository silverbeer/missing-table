-- Filter facets for a tournament's matches (SB-1749)
--
-- The Tournaments page pages a big event server-side (MLS NEXT Fest is ~2,400
-- matches; one PostgREST response is capped at 1,000 rows), so the Age Group
-- and Group controls can no longer be built from the rows the page happens to
-- hold. This answers "which age groups and groups exist here, with how many
-- matches each" in one aggregate, exact at any size.
--
-- Rows come back in two kinds, told apart by `facet`:
--
--   'age_group'  one per age group with matches in the tournament.
--                `matches_on_date` counts the ones played on p_on_date (0 when
--                p_on_date is NULL) — the page opens on the age group playing
--                today.
--   'group'      one per distinct tournament_group among group_stage matches,
--                narrowed to p_age_group_id when given. Stage labels on other
--                rounds ('HD · Showcase', 'GA Cup Qualifier') are not groups
--                and are left out, so a showcase-only age group has none.
--
-- Test fixtures (SB-591) are excluded through matches_with_test.is_test unless
-- p_include_test, the same rule the DAO applies to the match list.
--
-- SECURITY INVOKER (the default), like agent_match_summary and
-- agent_bootstrap_divisions: it reads only what the caller could already
-- select through matches_with_test, which is itself security_invoker.
--
-- The code ships separately from this migration. Until it is applied the DAO
-- reports the facets as unavailable and the page builds its Age Group control
-- from the tournament's own age groups, with no counts and no Group control.

CREATE INDEX IF NOT EXISTS idx_matches_tournament_age_date
    ON public.matches (tournament_id, age_group_id, match_date)
    WHERE tournament_id IS NOT NULL;

CREATE OR REPLACE FUNCTION public.tournament_filter_facets(
    p_tournament_id integer,
    p_age_group_id integer DEFAULT NULL,
    p_include_test boolean DEFAULT false,
    p_on_date date DEFAULT NULL
)
RETURNS TABLE (
    facet text,
    age_group_id integer,
    age_group_name text,
    tournament_group text,
    matches bigint,
    matches_on_date bigint
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
    SELECT
        'age_group'::text,
        m.age_group_id,
        ag.name::text,
        NULL::text,
        count(*),
        count(*) FILTER (WHERE m.match_date = p_on_date)
    FROM public.matches_with_test m
    JOIN public.age_groups ag ON ag.id = m.age_group_id
    WHERE m.tournament_id = p_tournament_id
      AND (p_include_test OR NOT m.is_test)
    GROUP BY m.age_group_id, ag.name

    UNION ALL

    SELECT
        'group'::text,
        NULL::integer,
        NULL::text,
        m.tournament_group,
        count(*),
        NULL::bigint
    FROM public.matches_with_test m
    WHERE m.tournament_id = p_tournament_id
      AND (p_include_test OR NOT m.is_test)
      AND (p_age_group_id IS NULL OR m.age_group_id = p_age_group_id)
      AND m.tournament_round = 'group_stage'
      AND btrim(COALESCE(m.tournament_group, '')) <> ''
    GROUP BY m.tournament_group;
$$;

COMMENT ON FUNCTION public.tournament_filter_facets IS
    'Age groups and group-stage groups of a tournament with exact match counts, '
    'for the Tournaments page filters (SB-1749). Test fixtures excluded unless '
    'p_include_test.';

-- Matches agent_match_summary: the DAO falls back to the anon key when
-- SUPABASE_SERVICE_KEY is absent, and the data is already publicly readable
-- through GET /api/tournaments/{id}.
GRANT EXECUTE ON FUNCTION public.tournament_filter_facets(integer, integer, boolean, date)
    TO anon, authenticated, service_role;
