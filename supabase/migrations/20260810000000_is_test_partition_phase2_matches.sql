-- Prod test partition (SB-591, Phase 2): matches and match-derived views.
--
-- Phase 1 (SB-85, 20260601100000_add_is_test_partition.sql) added is_test to
-- leagues, clubs, tournaments and user_profiles, and filtered the two list
-- endpoints (/api/leagues, /api/tournaments). It did NOT hide the matches
-- inside a test league — so seeding TSC matches in prod would surface fake
-- fixtures in real users' match lists, standings and leaderboards.
--
-- Derivation rule (decided here, SB-591): a match is test content iff ANY of
--
--   * its division's league is_test          (division_id -> divisions -> leagues)
--   * its tournament is_test                 (tournament_id -> tournaments)
--   * its home team's club is_test           (home_team_id -> teams -> clubs)
--   * its away team's club is_test           (away_team_id -> teams -> clubs)
--   * either team's own league is_test       (teams.league_id -> leagues)
--
-- The last three matter independently of the first two: matches.division_id and
-- matches.tournament_id are both nullable (ON DELETE SET NULL), so a friendly
-- with neither set has no competition path at all and is classified purely by
-- its clubs/teams. Conversely a test club can be entered into a real division,
-- which the competition paths alone would miss. Every path is checked.
--
-- Why a view and not a column on matches. The three paths are an OR across two
-- *separate* embedded relationships. PostgREST cannot express that in a single
-- query against public.matches (an `or=` filter may not span embedded resources),
-- so the Phase 1 one-liner `query.eq("is_test", False)` does not transfer. The
-- alternative — a denormalised matches.is_test column — needs triggers fanning
-- out over five tables (matches, teams, clubs, divisions, leagues) and drifts
-- silently the moment one is missed. The view computes the flag at read time
-- from the single source of truth, so it cannot drift.
--
-- The view exposes matches.* unchanged plus the derived is_test, so callers
-- swap only the relation name:
--
--     .table("matches")            ->  .table("matches_with_test")
--     ... plus  .eq("is_test", False)  for non-test viewers
--
-- Embedded selects (home_team:teams!matches_home_team_id_fkey(...), division ->
-- leagues, etc.) resolve from the view unchanged: PostgREST infers view
-- relationships from the base-table columns the view exposes, and the existing
-- FK-name hints still match. Verified against PostgREST on the local stack.
--
-- Writes are unaffected — inserts/updates/deletes continue to target
-- public.matches directly. This view is read-only by construction (it has
-- joins, so it is not auto-updatable) and no rule/trigger makes it writable.

CREATE VIEW public.matches_with_test
WITH (security_invoker = true)
AS
SELECT
    m.*,
    (
        COALESCE(l.is_test,  false)   -- division -> league
     OR COALESCE(tr.is_test, false)   -- tournament
     OR COALESCE(hc.is_test, false)   -- home team -> club
     OR COALESCE(ac.is_test, false)   -- away team -> club
     OR COALESCE(hl.is_test, false)   -- home team -> league
     OR COALESCE(al.is_test, false)   -- away team -> league
    ) AS is_test
FROM public.matches m
LEFT JOIN public.divisions   d  ON d.id  = m.division_id
LEFT JOIN public.leagues     l  ON l.id  = d.league_id
LEFT JOIN public.tournaments tr ON tr.id = m.tournament_id
LEFT JOIN public.teams       ht ON ht.id = m.home_team_id
LEFT JOIN public.clubs       hc ON hc.id = ht.club_id
LEFT JOIN public.leagues     hl ON hl.id = ht.league_id
LEFT JOIN public.teams       at ON at.id = m.away_team_id
LEFT JOIN public.clubs       ac ON ac.id = at.club_id
LEFT JOIN public.leagues     al ON al.id = at.league_id;

COMMENT ON VIEW public.matches_with_test IS
    'public.matches plus a derived is_test flag: true when the match''s league, '
    'tournament, either club or either team''s league is is_test (SB-591 '
    'Phase 2). Read path only; write to public.matches. Non-test, non-admin '
    'viewers must filter is_test = false.';

-- Every join is on an indexed primary key (divisions.id, leagues.id,
-- tournaments.id, teams.id, clubs.id), so the derivation is PK lookups per
-- match row. The one FK column not already covered is matches.division_id;
-- index it so division-scoped match queries stay on an index path.
CREATE INDEX IF NOT EXISTS idx_matches_division_id
    ON public.matches (division_id);

-- Partial indexes on the (small) test sets, mirroring the Phase 1 convention.
-- clubs had is_test added in Phase 1 but was never indexed, because Phase 1
-- never filtered on it; Phase 2 does, on every match read.
CREATE INDEX IF NOT EXISTS idx_clubs_is_test
    ON public.clubs (is_test) WHERE is_test;

GRANT SELECT ON public.matches_with_test TO anon, authenticated, service_role;

-- get_team_game_counts() aggregates public.matches directly, so it counted test
-- fixtures toward every team's game count regardless of viewer. Re-point it at
-- the view and gate it the same way as the DAO reads.
--
-- Adding a parameter creates an overload rather than replacing, so the old
-- zero-argument function must be dropped first. The new one keeps a DEFAULT so
-- existing `rpc("get_team_game_counts")` calls with no arguments still resolve.
DROP FUNCTION IF EXISTS public.get_team_game_counts();

CREATE OR REPLACE FUNCTION public.get_team_game_counts(p_include_test boolean DEFAULT false)
RETURNS TABLE(team_id integer, game_count bigint)
LANGUAGE plpgsql
STABLE
AS $function$
BEGIN
    RETURN QUERY
    WITH visible AS (
        SELECT m.home_team_id, m.away_team_id
        FROM public.matches_with_test m
        WHERE p_include_test OR NOT m.is_test
    ),
    home_games AS (
        SELECT visible.home_team_id AS tid, COUNT(*) AS count
        FROM visible
        GROUP BY visible.home_team_id
    ),
    away_games AS (
        SELECT visible.away_team_id AS tid, COUNT(*) AS count
        FROM visible
        GROUP BY visible.away_team_id
    ),
    combined AS (
        SELECT home_games.tid, home_games.count FROM home_games
        UNION ALL
        SELECT away_games.tid, away_games.count FROM away_games
    )
    SELECT
        combined.tid::INT AS team_id,
        SUM(combined.count)::BIGINT AS game_count
    FROM combined
    GROUP BY combined.tid;
END;
$function$;

-- NOTE: the ::BIGINT cast above is a bug fix, not cosmetics. SUM() over a
-- bigint returns numeric, so the previous definition raised "structure of query
-- does not match function result type" on every call. The DAO masked it with a
-- Python fallback (`if not response.data`), so team game counts have silently
-- been computed client-side rather than in Postgres. Fixed here because SB-591
-- had to redefine the function anyway.

GRANT EXECUTE ON FUNCTION public.get_team_game_counts(boolean)
    TO anon, authenticated, service_role;
