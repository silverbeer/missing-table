-- Tests for public.agent_match_summary (SB-1057)
--
-- CI does not start a database, so this does not run there. It is written to be
-- runnable against any empty Postgres in under a minute, which is the only way
-- the function gets checked at all — and the counting rules in it are the ones
-- the whole scraper schedule turns on:
--
--   PW=$(openssl rand -hex 16)
--   docker run -d --name pg -e POSTGRES_PASSWORD="$PW" -e POSTGRES_DB=test \
--     -p 55432:5432 postgres:16-alpine
--   PGPASSWORD="$PW" psql -h 127.0.0.1 -p 55432 -U postgres -d test \
--     -f supabase/tests/agent_match_summary_test.sql
--   docker rm -f pg
--
-- Fixture mirrors the shape the function depends on, including the six is_test
-- sources behind matches_with_test (SB-591), so the test-partition exclusion is
-- exercised through both a league and a club. It is a stand-in, not the real
-- schema: if the real view gains an is_test source, add it here too.
--
-- Reference clock throughout: now = 2026-09-12 18:00Z (Sat 14:00 ET),
-- today = 2026-09-12, grace = 3h.

\set ON_ERROR_STOP on

-- Minimal stand-in for the real schema: just enough for the function under test.
CREATE TYPE match_status AS ENUM ('scheduled','tbd','completed','forfeit','cancelled','live');
CREATE TABLE leagues    (id int PRIMARY KEY, name text, is_test boolean DEFAULT false);
CREATE TABLE age_groups (id int PRIMARY KEY, name text);
CREATE TABLE divisions  (id int PRIMARY KEY, name text, league_id int REFERENCES leagues(id));
CREATE TABLE clubs      (id int PRIMARY KEY, name text, is_test boolean DEFAULT false);
CREATE TABLE teams      (id int PRIMARY KEY, name text, club_id int REFERENCES clubs(id), league_id int REFERENCES leagues(id));
CREATE TABLE tournaments(id int PRIMARY KEY, name text, is_test boolean DEFAULT false);
CREATE TABLE matches (
    id int PRIMARY KEY,
    season_id int,
    match_date date,
    match_status match_status,
    home_score int,
    away_score int,
    scheduled_kickoff timestamptz,
    age_group_id int REFERENCES age_groups(id),
    division_id int REFERENCES divisions(id),
    tournament_id int REFERENCES tournaments(id),
    home_team_id int REFERENCES teams(id),
    away_team_id int REFERENCES teams(id)
);

-- Mirrors the real view's is_test derivation (SB-591).
CREATE VIEW matches_with_test AS
SELECT m.*,
  (COALESCE(l.is_test,false) OR COALESCE(tr.is_test,false)
   OR COALESCE(hc.is_test,false) OR COALESCE(ac.is_test,false)
   OR COALESCE(hl.is_test,false) OR COALESCE(al.is_test,false)) AS is_test
FROM matches m
LEFT JOIN divisions d ON d.id = m.division_id
LEFT JOIN leagues l ON l.id = d.league_id
LEFT JOIN tournaments tr ON tr.id = m.tournament_id
LEFT JOIN teams ht ON ht.id = m.home_team_id
LEFT JOIN clubs hc ON hc.id = ht.club_id
LEFT JOIN leagues hl ON hl.id = ht.league_id
LEFT JOIN teams at ON at.id = m.away_team_id
LEFT JOIN clubs ac ON ac.id = at.club_id
LEFT JOIN leagues al ON al.id = at.league_id;

INSERT INTO leagues VALUES (1,'Homegrown',false),(2,'Flex',false),(9,'TestLeague',true);
INSERT INTO age_groups VALUES (1,'U14'),(2,'U15');
INSERT INTO divisions VALUES (1,'Northeast',1),(2,'Florida',1),(3,'New England',2),(9,'TestDiv',9);
INSERT INTO clubs VALUES (1,'IFA',false),(9,'TestClub',true);
INSERT INTO teams VALUES (1,'IFA U14',1,1),(2,'Revs U14',1,1),(9,'Test Team',9,9);

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

-- now = 2026-09-12 18:00Z (Sat 14:00 ET), today = 2026-09-12, grace = 3h
INSERT INTO matches (id,season_id,match_date,match_status,home_score,away_score,scheduled_kickoff,age_group_id,division_id,home_team_id,away_team_id) VALUES
 -- U14 Homegrown Northeast
 (1, 1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 13:00Z',1,1,1,2),  -- 5h ago  -> DUE
 (2, 1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 17:45Z',1,1,1,2),  -- 15m ago -> not due
 (3, 1,'2026-09-12','completed',2,   1,   '2026-09-12 13:00Z',1,1,1,2),  -- scored  -> not due, last_played
 (4, 1,'2026-09-11','scheduled',NULL,NULL,NULL,               1,1,1,2),  -- no kickoff, yesterday -> DUE via date fallback
 (5, 1,'2026-10-01','scheduled',NULL,NULL,NULL,               1,1,1,2),  -- future, beyond horizon
 (6, 1,'2026-09-20','scheduled',NULL,NULL,NULL,               1,1,1,2),  -- within 14d, no kickoff -> needs_kickoff
 (7, 1,'2026-12-01','scheduled',NULL,NULL,NULL,               1,1,1,2),  -- beyond horizon
 (8, 1,'2026-09-05','scheduled',NULL,NULL,'2026-09-05 13:00Z',1,1,1,2),  -- past+unscored but OUTSIDE score window
 (9, 1,'2026-09-12','cancelled',NULL,NULL,'2026-09-12 13:00Z',1,1,1,2),  -- cancelled -> excluded entirely
 -- test partition: league is_test, must be excluded
 (10,1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 13:00Z',1,9,1,2),
 -- test partition: away team's club is_test, must be excluded
 (11,1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 13:00Z',1,1,1,9),
 -- a different group entirely
 (12,1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 12:00Z',2,3,1,2),
 -- another season, must not leak in
 (13,2,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 12:00Z',1,1,1,2);
INSERT INTO matches (id,season_id,match_date,match_status,home_score,away_score,scheduled_kickoff,age_group_id,division_id,home_team_id,away_team_id)
VALUES (20,1,'2026-09-12','scheduled',NULL,NULL,'2026-09-12 12:00Z',NULL,NULL,1,2);  -- no division, no age group

DO $test$
DECLARE
    r record;
    n bigint;
BEGIN
    -- ---- the main group -------------------------------------------------
    SELECT * INTO r FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13')
        WHERE division = 'Northeast';

    ASSERT r.total = 8,
        format('total: cancelled, test-partition and other-season rows must all be excluded, got %s', r.total);
    ASSERT r.by_status = '{"completed": 1, "scheduled": 7}'::jsonb,
        format('by_status: %s', r.by_status);
    ASSERT r.needs_score = 2,
        format('needs_score: kicked off 5h ago, plus yesterday with no kick-off time; got %s', r.needs_score);
    ASSERT r.needs_kickoff = 1,
        format('needs_kickoff: only the fixture inside the horizon missing a time; got %s', r.needs_kickoff);
    ASSERT r.earliest = '2026-09-05' AND r.latest = '2026-12-01',
        'date_range stays season-wide, not narrowed by the score window';
    ASSERT r.last_played_date = '2026-09-12',
        format('last_played_date: %s', r.last_played_date);

    -- ---- the grace boundary is inclusive --------------------------------
    SELECT needs_score INTO n FROM public.agent_match_summary(
        1,'2026-09-12 16:00Z','2026-09-12','2026-09-11','2026-09-13') WHERE division='Northeast';
    ASSERT n = 2, format('kick-off exactly one grace ago must count, got %s', n);

    SELECT needs_score INTO n FROM public.agent_match_summary(
        1,'2026-09-12 15:59:59Z','2026-09-12','2026-09-11','2026-09-13') WHERE division='Northeast';
    ASSERT n = 1, format('one second short of the grace must not count, got %s', n);

    -- ---- the window narrows needs_score, and only that ------------------
    SELECT needs_score INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12') WHERE division='Northeast';
    ASSERT n = 3, format('with no window the older unscored match counts too, got %s', n);

    -- ---- grace and horizon are honoured as parameters -------------------
    SELECT needs_score INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13',p_score_grace=>'12 hours') WHERE division='Northeast';
    ASSERT n = 1, format('a longer grace makes fewer scores due, got %s', n);

    SELECT needs_kickoff INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13',p_kickoff_horizon_days=>30) WHERE division='Northeast';
    ASSERT n = 2, format('a wider horizon reaches the later fixture, got %s', n);

    -- ---- the test partition (SB-591) ------------------------------------
    SELECT total INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13',p_include_test=>true) WHERE division='Northeast';
    ASSERT n = 9, format('include_test pulls back the row whose away club is test, got %s', n);

    SELECT count(*) INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13') WHERE division='TestDiv';
    ASSERT n = 0, 'a division under a test league must not appear by default';

    -- ---- rows with nothing to group by ----------------------------------
    -- 23 such rows exist in the live 2026-2027 season; the Python path this
    -- replaces labelled them Unknown and the planner skips them.
    SELECT total INTO n FROM public.agent_match_summary(
        1,'2026-09-12 18:00Z','2026-09-12','2026-09-11','2026-09-13')
        WHERE age_group='Unknown' AND league='Unknown' AND division='Unknown';
    ASSERT n = 1, format('a match with no division or age group must group as Unknown, got %s', n);

    -- ---- an unknown season is empty, not an error -----------------------
    SELECT count(*) INTO n FROM public.agent_match_summary(999,'2026-09-12 18:00Z','2026-09-12');
    ASSERT n = 0, 'an unknown season returns no rows';

    RAISE NOTICE 'agent_match_summary: all assertions passed';
END
$test$;
