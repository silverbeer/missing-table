-- TSC test world seed (SB-592).
--
-- Creates a self-contained, repeatable test world so the Android live-scoring
-- app can be rehearsed against real prod infrastructure before a real match.
-- Everything it creates is is_test content, hidden from real viewers by the
-- SB-591 partition (public.matches_with_test).
--
-- Run it with scripts/tsc_test_world.sh — that wrapper carries the environment
-- guard and the post-run verification. This file is safe to run repeatedly:
-- every statement is idempotent.
--
-- WHAT IT TOUCHES
--
--   clubs      — ensures one is_test club ("Toms Soccer Club")
--   leagues    — ensures one is_test league ("TSC League 1") + a division
--   teams      — ensures TSC A/B/C/D-Team, all attached to the test club
--   players    — 16 per team (11 starters + 5 bench), jersey 1..16
--   matches    — the dry-run fixtures, tagged match_id = 'TSC-DRYRUN-<n>'
--
-- It never writes a row that is not reachable from the is_test club/league, and
-- it never deletes anything except matches whose match_id starts with
-- 'TSC-DRYRUN-' (see scripts/tsc_test_world.sh reset).
--
-- WHY C-TEAM AND D-TEAM ARE RE-PARENTED
--
-- Both were created with club_id, league_id and division_id all NULL. Nothing
-- about them is flagged, so the partition could only hide their matches via the
-- tournament path — a plain C-vs-D friendly with no tournament and no division
-- would have been VISIBLE to real users. Attaching them to the test club closes
-- that: every TSC team now carries the flag through both club and league.

\set ON_ERROR_STOP on

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Anchors. Resolved by flag/name rather than hardcoded id so this works
--    against a fresh local DB as well as prod.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE tsc_anchor ON COMMIT DROP AS
SELECT
    (SELECT id FROM seasons    WHERE is_current ORDER BY id LIMIT 1)          AS season_id,
    (SELECT id FROM age_groups WHERE name = 'U14' ORDER BY id LIMIT 1)        AS age_group_id,
    (SELECT id FROM match_types WHERE name = 'Friendly' ORDER BY id LIMIT 1)  AS friendly_id;

DO $$
BEGIN
    IF (SELECT season_id FROM tsc_anchor) IS NULL THEN
        RAISE EXCEPTION 'No current season (seasons.is_current) — seed the base data first';
    END IF;
    IF (SELECT age_group_id FROM tsc_anchor) IS NULL THEN
        RAISE EXCEPTION 'No U14 age group — seed the base data first';
    END IF;
    IF (SELECT friendly_id FROM tsc_anchor) IS NULL THEN
        RAISE EXCEPTION 'No Friendly match type — seed the base data first';
    END IF;
END $$;

-- Club. Reuse the existing test club if it is already there.
INSERT INTO clubs (name, city, is_test)
SELECT 'Toms Soccer Club', 'Testville', true
WHERE NOT EXISTS (SELECT 1 FROM clubs WHERE name = 'Toms Soccer Club');

UPDATE clubs SET is_test = true WHERE name = 'Toms Soccer Club' AND is_test IS DISTINCT FROM true;

-- League + division.
INSERT INTO leagues (name, is_active, is_test)
SELECT 'TSC League 1', true, true
WHERE NOT EXISTS (SELECT 1 FROM leagues WHERE name = 'TSC League 1');

UPDATE leagues SET is_test = true WHERE name = 'TSC League 1' AND is_test IS DISTINCT FROM true;

INSERT INTO divisions (name, league_id)
SELECT 'TSC Division 1', (SELECT id FROM leagues WHERE name = 'TSC League 1')
WHERE NOT EXISTS (
    SELECT 1 FROM divisions
    WHERE league_id = (SELECT id FROM leagues WHERE name = 'TSC League 1')
);

CREATE TEMP TABLE tsc_ids ON COMMIT DROP AS
SELECT
    (SELECT id FROM clubs   WHERE name = 'Toms Soccer Club')  AS club_id,
    (SELECT id FROM leagues WHERE name = 'TSC League 1')      AS league_id,
    (SELECT d.id FROM divisions d
       WHERE d.league_id = (SELECT id FROM leagues WHERE name = 'TSC League 1')
       ORDER BY d.id LIMIT 1)                                 AS division_id;

-- ---------------------------------------------------------------------------
-- 2. Teams. Create the four squads if absent, then (re-)attach every one of
--    them to the test club/league/division. The UPDATE is the part that closes
--    the C/D-Team leak described in the header.
-- ---------------------------------------------------------------------------

INSERT INTO teams (name, city)
SELECT v.name, 'Testville'
FROM (VALUES ('TSC A-Team'), ('TSC B-Team'), ('TSC C-Team'), ('TSC D-Team')) AS v(name)
WHERE NOT EXISTS (SELECT 1 FROM teams t WHERE t.name = v.name);

UPDATE teams t
   SET club_id     = (SELECT club_id     FROM tsc_ids),
       league_id   = (SELECT league_id   FROM tsc_ids),
       division_id = (SELECT division_id FROM tsc_ids),
       age_group_id = (SELECT age_group_id FROM tsc_anchor)
 WHERE t.name IN ('TSC A-Team', 'TSC B-Team', 'TSC C-Team', 'TSC D-Team')
   AND (t.club_id      IS DISTINCT FROM (SELECT club_id     FROM tsc_ids)
     OR t.league_id    IS DISTINCT FROM (SELECT league_id   FROM tsc_ids)
     OR t.division_id  IS DISTINCT FROM (SELECT division_id FROM tsc_ids)
     OR t.age_group_id IS DISTINCT FROM (SELECT age_group_id FROM tsc_anchor));

CREATE TEMP TABLE tsc_teams ON COMMIT DROP AS
SELECT id, name,
       substring(name from 'TSC (.)-Team') AS letter
FROM teams
WHERE name IN ('TSC A-Team', 'TSC B-Team', 'TSC C-Team', 'TSC D-Team');

-- ---------------------------------------------------------------------------
-- 3. Rosters. 16 per squad: 11 starters + 5 on the bench, so a substitution is
--    a real decision rather than the only option. Jersey numbers 1..16 — the
--    scorer grid is navigated by number under time pressure, so they must be
--    present and stable across reseeds.
--
--    Names are "<Letter><n> Tester" (e.g. "A7 Tester") so a human watching a
--    dry run can tell instantly which squad a tile belongs to.
-- ---------------------------------------------------------------------------

INSERT INTO players (team_id, season_id, age_group_id, jersey_number,
                     first_name, last_name, positions, is_active)
SELECT
    t.id,
    (SELECT season_id    FROM tsc_anchor),
    (SELECT age_group_id FROM tsc_anchor),
    n.jersey,
    t.letter || n.jersey::text,
    'Tester',
    ARRAY[n.position],
    true
FROM tsc_teams t
CROSS JOIN (VALUES
    ( 1, 'GK'),  ( 2, 'RB'),  ( 3, 'LB'),  ( 4, 'CB'),
    ( 5, 'CB'),  ( 6, 'CDM'), ( 7, 'RM'),  ( 8, 'CM'),
    ( 9, 'ST'),  (10, 'CAM'), (11, 'LM'),
    -- bench
    (12, 'GK'),  (13, 'CB'),  (14, 'CM'),  (15, 'RW'), (16, 'ST')
) AS n(jersey, position)
ON CONFLICT (team_id, season_id, age_group_id, jersey_number) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 4. Fixtures.
--
--    The point of these is that a dry run needs NO setup: there is always a
--    match sitting at kickoff. Offsets are relative to now(), so a reseed rolls
--    them forward rather than leaving a stale June fixture behind — and
--    match_date is derived FROM the kickoff instant rather than set alongside
--    it, so the two can never disagree.
--
--      TSC-DRYRUN-1  A vs B  — kicked off 30 min ago; start scoring immediately
--      TSC-DRYRUN-2  C vs D  — in 3 hours, a second bite without a reseed
--      TSC-DRYRUN-3  A vs C  — tomorrow
--      TSC-DRYRUN-4  B vs D  — in three days
--
--    match_id is the external-identifier column; prefixing with TSC-DRYRUN-
--    gives the reset path an exact, safe key to delete on.
-- ---------------------------------------------------------------------------

CREATE TEMP TABLE tsc_fixtures ON COMMIT DROP AS
SELECT
    f.ext_id,
    f.home_name,
    f.away_name,
    (now() + f.kick_at) AS kickoff
FROM (VALUES
    ('TSC-DRYRUN-1', INTERVAL '-30 minutes', 'TSC A-Team', 'TSC B-Team'),
    ('TSC-DRYRUN-2', INTERVAL '3 hours',     'TSC C-Team', 'TSC D-Team'),
    ('TSC-DRYRUN-3', INTERVAL '1 day',       'TSC A-Team', 'TSC C-Team'),
    ('TSC-DRYRUN-4', INTERVAL '3 days',      'TSC B-Team', 'TSC D-Team')
) AS f(ext_id, kick_at, home_name, away_name);

INSERT INTO matches (
    match_id, match_date, scheduled_kickoff,
    home_team_id, away_team_id,
    season_id, age_group_id, match_type_id, division_id,
    match_status, home_score, away_score, source
)
SELECT
    f.ext_id,
    f.kickoff::date,
    f.kickoff,
    home.id, away.id,
    (SELECT season_id    FROM tsc_anchor),
    (SELECT age_group_id FROM tsc_anchor),
    (SELECT friendly_id  FROM tsc_anchor),
    (SELECT division_id  FROM tsc_ids),
    'scheduled', NULL, NULL, 'manual'
FROM tsc_fixtures f
JOIN tsc_teams home ON home.name = f.home_name
JOIN tsc_teams away ON away.name = f.away_name
WHERE NOT EXISTS (SELECT 1 FROM matches m WHERE m.match_id = f.ext_id);

-- Roll an existing dry-run fixture forward so a reseed always leaves one at
-- kickoff, and clear any score/clock state left behind by the last rehearsal.
UPDATE matches m
   SET match_date        = f.kickoff::date,
       scheduled_kickoff = f.kickoff,
       match_status      = 'scheduled',
       home_score        = NULL,
       away_score        = NULL,
       kickoff_time      = NULL,
       halftime_start    = NULL,
       second_half_start = NULL,
       match_end_time    = NULL
FROM tsc_fixtures f
WHERE m.match_id = f.ext_id;

-- ---------------------------------------------------------------------------
-- 5. Assert the partition actually covers everything just written. If any of
--    it would be visible to a real viewer, fail the transaction rather than
--    leave test data leaking into prod.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    leaked integer;
BEGIN
    SELECT count(*) INTO leaked
    FROM public.matches_with_test m
    WHERE m.match_id LIKE 'TSC-DRYRUN-%'
      AND NOT m.is_test;

    IF leaked > 0 THEN
        RAISE EXCEPTION
            'ABORT: % seeded fixture(s) are visible to real viewers — the is_test '
            'derivation does not cover them. Nothing was written.', leaked;
    END IF;
END $$;

COMMIT;
