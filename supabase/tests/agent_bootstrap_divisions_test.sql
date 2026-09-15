-- Tests for public.agent_bootstrap_divisions (SB-1080)
--
-- CI does not start a database, so this does not run there. Like
-- agent_match_summary_test.sql it runs against any empty Postgres in seconds,
-- from the repo root:
--
--   PW=$(openssl rand -hex 16)
--   docker run -d --name pg -e POSTGRES_PASSWORD="$PW" -e POSTGRES_DB=test \
--     -p 55432:5432 postgres:16-alpine
--   PGPASSWORD="$PW" psql -h 127.0.0.1 -p 55432 -U postgres -d test \
--     -f supabase/tests/agent_bootstrap_divisions_test.sql
--   docker rm -f pg
--
-- Unlike that test it loads the real migration file rather than a copy, so the
-- function tested is the function shipped. The stand-in schema holds only the
-- columns the function reads, plus the Supabase roles its GRANT names.

\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role; END IF;
END
$$;

CREATE TYPE match_status AS ENUM ('scheduled','tbd','completed','forfeit','cancelled','live');
CREATE TABLE leagues (
    id int PRIMARY KEY,
    name text NOT NULL,
    is_active boolean DEFAULT true,
    is_test boolean NOT NULL DEFAULT false
);
CREATE TABLE divisions (id int PRIMARY KEY, name text NOT NULL, league_id int NOT NULL REFERENCES leagues(id));
CREATE TABLE matches (id int PRIMARY KEY, season_id int, division_id int REFERENCES divisions(id), match_status match_status);

\ir ../migrations/20260915000000_agent_bootstrap_divisions_fn.sql

-- Season 1 is the season asked about; season 2 is last season.
INSERT INTO leagues (id, name, is_active, is_test) VALUES
    (1, 'Homegrown',   true,  false),
    (2, 'Flex',        true,  false),
    (3, 'Kick Futsal', false, false),  -- retired
    (4, 'TSC League',  true,  true),   -- test partition
    (5, 'Legacy',      NULL,  false),  -- is_active never set
    (6, 'academy',     true,  false);  -- lower case: sorts after upper case by code point

INSERT INTO divisions (id, name, league_id) VALUES
    (10, 'Northeast',    1),  -- has a match this season
    (11, 'Southwest',    1),  -- only a cancelled match this season
    (12, 'Mid-Atlantic', 1),  -- matches last season only
    (20, 'Turnpike',     2),  -- nothing
    (21, 'Empire',       2),  -- nothing
    (23, 'Nullstatus',   2),  -- a match this season with no status
    (30, 'Bracket A',    3),  -- retired league
    (40, 'TSC Top',      4),  -- test league
    (50, 'Old',          5),  -- league with NULL is_active
    (60, 'Pacific',      6);

INSERT INTO matches (id, season_id, division_id, match_status) VALUES
    (1, 1, 10, 'completed'),
    (2, 1, 11, 'cancelled'),
    (3, 2, 12, 'completed'),
    (4, 1, 23, NULL),
    (5, 1, NULL, 'scheduled');  -- a match with no division seeds nothing

DO $test$
DECLARE
    ids int[];
    r record;
BEGIN
    -- ---- the list the agent gets --------------------------------------------
    SELECT array_agg(t.division_id ORDER BY t.ord) INTO ids
    FROM public.agent_bootstrap_divisions(1, false) WITH ORDINALITY AS t(division_id, division, league, ord);
    ASSERT ids = ARRAY[21, 23, 20, 12, 11, 60],
        format('unseeded divisions, league then division by code point: expected {21,23,20,12,11,60}, got %s', ids);

    -- ---- each rule on its own -----------------------------------------------
    ASSERT NOT (10 = ANY(ids)), 'a division with a match this season is not offered';
    ASSERT 11 = ANY(ids), 'a cancelled match does not seed a division';
    ASSERT 12 = ANY(ids), 'last season''s matches do not seed this season';
    ASSERT 23 = ANY(ids), 'a match with no status does not seed a division (PostgREST neq excluded NULLs)';
    ASSERT NOT (30 = ANY(ids)), 'a retired league is never offered';
    ASSERT NOT (50 = ANY(ids)), 'a league whose is_active was never set is not offered';
    ASSERT NOT (40 = ANY(ids)), 'a test league is hidden from real viewers';

    -- ---- test viewers see the test league, in its place ---------------------
    SELECT array_agg(t.division_id ORDER BY t.ord) INTO ids
    FROM public.agent_bootstrap_divisions(1, true) WITH ORDINALITY AS t(division_id, division, league, ord);
    ASSERT ids = ARRAY[21, 23, 20, 12, 11, 40, 60],
        format('with test content: expected {21,23,20,12,11,40,60}, got %s', ids);

    -- ---- the row carries names, not just ids --------------------------------
    SELECT * INTO r FROM public.agent_bootstrap_divisions(1, false) WHERE division_id = 20;
    ASSERT r.division = 'Turnpike' AND r.league = 'Flex',
        format('row shape: expected (20, Turnpike, Flex), got %s', r);

    -- ---- an unknown season has no matches, so every active division ---------
    SELECT array_agg(t.division_id ORDER BY t.ord) INTO ids
    FROM public.agent_bootstrap_divisions(999) WITH ORDINALITY AS t(division_id, division, league, ord);
    ASSERT ids = ARRAY[21, 23, 20, 12, 10, 11, 60],
        format('unknown season: expected every active real division, got %s', ids);

    RAISE NOTICE 'agent_bootstrap_divisions: all assertions passed';
END
$test$;
