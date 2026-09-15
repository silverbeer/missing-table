-- The agent's match summary, computed in the database (SB-1057)
--
-- Same argument as competition_coverage (SB-1021) and record_ingest_failure
-- before it: the alternative is fetching every fixture in a season to count
-- them in application code. That is what get_match_summary did, and by
-- 2026-2027 it meant 5,272 rows in six paginated PostgREST round trips, each
-- row assembled through the nine LEFT JOINs behind matches_with_test and
-- decorated with three nested embeds, to produce 119 rows of counts.
--
-- 94% of those rows were fixtures nobody had played yet — 4,934 scheduled
-- against 335 completed — because needs_score can only ever count matches
-- inside the score window and needs_kickoff only the next fortnight. They were
-- fetched and then discarded by a Python loop.
--
-- It did not merely waste work, it broke. Supabase's gateway times a request
-- out at ~6-10s, so the first caller after an idle gap got a 504 which
-- PostgREST returned as "JSON could not be generated" and the endpoint
-- re-raised as HTTP 500. The scraper agent runs hours apart and is therefore
-- always that caller: it lost four consecutive production runs to this between
-- 2026-09-11T18:00Z and 2026-09-12T12:00Z, on a match weekend, because the
-- planner halts fail-fast without MT data. SB-1055 added a retry, which buys
-- time against a cliff that moves closer every time a fixture is added.
--
-- Three fields are deliberately season-wide rather than windowed: total,
-- by_status and last_played_date. The planner treats total = 0 as "new target,
-- sync the whole season", so narrowing it would make a target with no *recent*
-- matches look new and trigger a full-season scrape of everything. Computing
-- them costs nothing here — they are counts over the same single pass that the
-- windowed FILTERs use.
--
-- Test fixtures (SB-591) are excluded through matches_with_test.is_test, the
-- same way competition_coverage does it, so there stays exactly one definition
-- of what a test fixture is. Deriving it needs those nine joins wherever the
-- expression is written, so reading the view costs nothing over hand-rolling
-- it and avoids a second copy of the rule.
--
-- now/today/grace are parameters rather than now() and CURRENT_DATE so that the
-- caller owns the clock. SCORE_GRACE lives in Python (dao/match_dao.py) and is
-- passed in; a default here is a safety net, not a second source of truth.

CREATE OR REPLACE FUNCTION public.agent_match_summary(
    p_season_id integer,
    p_now timestamptz,
    p_today date,
    p_score_from date DEFAULT NULL,
    p_score_to date DEFAULT NULL,
    p_score_grace interval DEFAULT '3 hours',
    p_kickoff_horizon_days integer DEFAULT 14,
    p_include_test boolean DEFAULT false
)
RETURNS TABLE (
    age_group text,
    league text,
    division text,
    total bigint,
    by_status jsonb,
    needs_score bigint,
    needs_kickoff bigint,
    earliest date,
    latest date,
    last_played_date date
)
LANGUAGE sql
STABLE
AS $$
    WITH scoped AS (
        SELECT
            coalesce(ag.name, 'Unknown')::text AS age_group,
            coalesce(l.name, 'Unknown')::text  AS league,
            coalesce(d.name, 'Unknown')::text  AS division,
            m.match_status::text               AS match_status,
            m.match_date,
            m.home_score,
            m.scheduled_kickoff
        FROM public.matches_with_test m
        LEFT JOIN public.age_groups ag ON ag.id = m.age_group_id
        LEFT JOIN public.divisions  d  ON d.id  = m.division_id
        LEFT JOIN public.leagues    l  ON l.id  = d.league_id
        WHERE m.season_id = p_season_id
          AND m.match_status <> 'cancelled'
          AND (p_include_test OR m.is_test = false)
    ),
    -- Grouped one level deeper than the result so by_status can be built with
    -- jsonb_object_agg over real rows rather than a correlated subquery per
    -- group. The windowed counts ride along on the same pass.
    per_status AS (
        SELECT
            s.age_group,
            s.league,
            s.division,
            s.match_status,
            count(*) AS n,
            count(*) FILTER (
                WHERE s.match_status IN ('scheduled', 'tbd')
                  AND s.home_score IS NULL
                  AND (p_score_from IS NULL OR s.match_date >= p_score_from)
                  AND (p_score_to   IS NULL OR s.match_date <= p_score_to)
                  -- A score is due once the match has been over long enough to
                  -- have been entered, not once the calendar day has ended
                  -- (SB-1058). Falls back to the date when kick-off is unknown:
                  -- without a time there is no telling a finished match from
                  -- one that has not started.
                  AND CASE
                        WHEN s.scheduled_kickoff IS NOT NULL
                            THEN s.scheduled_kickoff + p_score_grace <= p_now
                        ELSE s.match_date < p_today
                      END
            ) AS needs_score,
            count(*) FILTER (
                WHERE s.match_status IN ('scheduled', 'tbd')
                  AND s.scheduled_kickoff IS NULL
                  AND s.match_date >= p_today
                  AND s.match_date <= p_today + p_kickoff_horizon_days
            ) AS needs_kickoff,
            min(s.match_date) AS earliest,
            max(s.match_date) AS latest,
            max(s.match_date) FILTER (
                WHERE s.match_status IN ('completed', 'forfeit')
            ) AS last_played
        FROM scoped s
        GROUP BY s.age_group, s.league, s.division, s.match_status
    )
    SELECT
        p.age_group,
        p.league,
        p.division,
        sum(p.n)::bigint AS total,
        jsonb_object_agg(p.match_status, p.n) AS by_status,
        sum(p.needs_score)::bigint AS needs_score,
        sum(p.needs_kickoff)::bigint AS needs_kickoff,
        min(p.earliest) AS earliest,
        max(p.latest) AS latest,
        max(p.last_played) AS last_played_date
    FROM per_status p
    GROUP BY p.age_group, p.league, p.division
    ORDER BY p.age_group, p.league, p.division;
$$;

COMMENT ON FUNCTION public.agent_match_summary IS
    'Per age-group/league/division match counts for the scraper agent. Replaces '
    'a 5,272-row fetch that tripped Supabase''s gateway timeout on every cold '
    'call (SB-1057). total/by_status/last_played_date are season-wide because '
    'the planner reads total = 0 as "sync the whole season"; needs_score and '
    'needs_kickoff are bounded by the parameters.';

-- Matches competition_coverage: the DAO falls back to the anon key when
-- SUPABASE_SERVICE_KEY is absent, and the endpoint's own permission dependency
-- is the real gate.
GRANT EXECUTE ON FUNCTION public.agent_match_summary(
    integer, timestamptz, date, date, date, interval, integer, boolean
) TO anon, authenticated, service_role;
