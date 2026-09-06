-- The coverage diff itself (SB-1021)
--
-- A database function rather than a Python loop, for the same reason
-- record_ingest_failure is one: the alternative is fetching every fixture in a
-- season to count them in application code, and a season is 3,162 rows and
-- growing.
--
-- It is a FULL OUTER JOIN on purpose. The left side alone answers "which
-- expected conferences got nothing" — the question that went unasked for a
-- season. The right side alone answers "what is arriving that nobody
-- declared", which is how a feed quietly changing shape gets noticed instead
-- of silently widening the database.
--
-- Test fixtures (SB-591) are excluded: a coverage report that counts them
-- would report a conference as covered on the strength of seed data.

CREATE OR REPLACE FUNCTION public.competition_coverage(p_season_id integer)
RETURNS TABLE (
    league_name text,
    division_id integer,
    division_name text,
    age_group_id integer,
    age_group_name text,
    is_expected boolean,
    fixtures bigint,
    played bigint,
    last_fixture date,
    teams_registered bigint
)
LANGUAGE sql
STABLE
AS $$
    WITH expected AS (
        SELECT dag.division_id, dag.age_group_id
        FROM public.division_age_groups dag
        WHERE dag.season_id = p_season_id
    ),
    actual AS (
        SELECT
            m.division_id,
            m.age_group_id,
            count(*) AS fixtures,
            count(*) FILTER (
                WHERE m.match_status IN ('completed', 'forfeit')
            ) AS played,
            max(m.match_date) AS last_fixture
        FROM public.matches_with_test m
        WHERE m.season_id = p_season_id
          AND m.is_test = false
          AND m.division_id IS NOT NULL
        GROUP BY m.division_id, m.age_group_id
    ),
    registered AS (
        SELECT tm.division_id, tm.age_group_id, count(*) AS teams
        FROM public.team_mappings tm
        GROUP BY tm.division_id, tm.age_group_id
    ),
    combined AS (
        SELECT
            coalesce(e.division_id, a.division_id) AS division_id,
            coalesce(e.age_group_id, a.age_group_id) AS age_group_id,
            (e.division_id IS NOT NULL) AS is_expected,
            coalesce(a.fixtures, 0) AS fixtures,
            coalesce(a.played, 0) AS played,
            a.last_fixture
        FROM expected e
        FULL OUTER JOIN actual a
          ON a.division_id = e.division_id
         AND a.age_group_id = e.age_group_id
    )
    SELECT
        l.name::text,
        c.division_id,
        d.name::text,
        c.age_group_id,
        ag.name::text,
        c.is_expected,
        c.fixtures,
        c.played,
        c.last_fixture::date,
        coalesce(r.teams, 0) AS teams_registered
    FROM combined c
    JOIN public.divisions d ON d.id = c.division_id
    JOIN public.leagues l ON l.id = d.league_id
    JOIN public.age_groups ag ON ag.id = c.age_group_id
    LEFT JOIN registered r
      ON r.division_id = c.division_id
     AND r.age_group_id = c.age_group_id
    ORDER BY l.name, d.name, ag.name;
$$;

COMMENT ON FUNCTION public.competition_coverage(integer) IS
    'SB-1021: expected conference/age-group coverage for a season joined against fixtures that actually arrived. is_expected=false means fixtures landed for a combination nobody declared.';

-- Readable by any signed-in caller, not just the service role. The backend
-- falls back to the anon key when SUPABASE_SERVICE_KEY is absent (see
-- SupabaseConnection in dao/match_dao.py), and a 403 there surfaces as
-- `available: false` — a coverage report that silently reports nothing is the
-- exact failure mode this feature exists to end. The data is derived from
-- public fixtures; `require_admin` on the endpoint is the real gate.
GRANT EXECUTE ON FUNCTION public.competition_coverage(integer) TO anon, authenticated, service_role;
