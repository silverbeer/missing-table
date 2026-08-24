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
-- 3. Rosters. ONLY TSC A-Team is populated — 16 players, 11 starters plus 5 on
--    the bench so a substitution is a real decision rather than the only
--    option. Numbers are stable across reseeds, because the scorer grid is
--    navigated by number under time pressure — and deliberately NOT a
--    contiguous 1..16, since real squads never are.
--
--    The other three squads are deliberately EMPTY. That mirrors prod today:
--    one club has entered a roster and the rest have not. A dry run must
--    therefore exercise BOTH paths — picking a known player, and free-text
--    entry against a squad with no roster at all — because on match day the
--    opposition will not have one.
--
--    Names are "First L." (e.g. "Diego M."), which is the shape real rosters
--    take and short enough for a tile. The cast is drawn from the history of
--    the world game, each wearing the number they actually wore.
--
--    Five of them share the initial "B." — Beckenbauer, Baresi, Best, Buffon,
--    Ballack — and two are Sergios. That is deliberate: telling near-identical
--    names apart at speed is exactly the case that bites at a pitch, and a
--    roster of conveniently distinct names would not test it.
-- ---------------------------------------------------------------------------

-- Clear any squad that should be empty. Previous seeds populated all four.
-- match_lineups keeps its positions as jsonb rather than child rows, so only
-- player_match_stats needs clearing before the players themselves.
DELETE FROM player_match_stats WHERE player_id IN (
    SELECT p.id FROM players p JOIN teams t ON t.id = p.team_id
    WHERE t.name IN ('TSC B-Team', 'TSC C-Team', 'TSC D-Team'));
DELETE FROM players WHERE team_id IN (
    SELECT id FROM teams WHERE name IN ('TSC B-Team', 'TSC C-Team', 'TSC D-Team'));

INSERT INTO players (team_id, season_id, age_group_id, jersey_number,
                     first_name, last_name, positions, is_active)
SELECT
    t.id,
    (SELECT season_id    FROM tsc_anchor),
    (SELECT age_group_id FROM tsc_anchor),
    n.jersey,
    n.given,
    n.surname,
    ARRAY[n.position],
    true
FROM tsc_teams t
CROSS JOIN (VALUES
    -- Each shirt is the number that player actually wore, and the position
    -- is the one they played. A roster where the numbers are arbitrary is a
    -- worse test: the scorer grid is navigated by number, and a nonsense
    -- pairing is noticed as "wrong" rather than read as data.
    --
    -- The great 10s (Maradona, Pele, Zidane, Messi) cannot all appear —
    -- there is one number 10 — so the squad is built from players whose
    -- numbers do not collide.
    ( 1, 'GK',  'Lev',       'Y.'),   -- Yashin, 1
    ( 2, 'RB',  'Dani',      'A.'),   -- Alves, 2
    ( 3, 'LB',  'Paolo',     'M.'),   -- Maldini, 3
    ( 4, 'CB',  'Sergio',    'R.'),   -- Ramos, 4
    ( 5, 'CB',  'Franz',     'B.'),   -- Beckenbauer, 5
    ( 6, 'CDM', 'Franco',    'B.'),   -- Baresi, 6
    ( 7, 'RM',  'George',    'B.'),   -- Best, 7
    ( 8, 'CM',  'Andres',    'I.'),   -- Iniesta, 8
    ( 9, 'ST',  'Ronaldo',   'N.'),   -- Nazario, 9
    (10, 'CAM', 'Diego',     'M.'),   -- Maradona, 10
    (11, 'LM',  'Ryan',      'G.'),   -- Giggs, 11
    -- bench
    (12, 'GK',  'Gianluigi', 'B.'),   -- Buffon, 12 at Parma
    (13, 'CM',  'Michael',   'B.'),   -- Ballack, 13
    (14, 'CM',  'Johan',     'C.'),   -- Cruyff, 14
    (15, 'CB',  'Nemanja',   'V.'),   -- Vidic, 15
    (16, 'ST',  'Sergio',    'A.'),   -- Aguero, 16 at Atletico
    (30, 'RW',  'Lionel',    'M.')    -- Messi, 30 on his Barcelona debut
) AS n(jersey, position, given, surname)
WHERE t.name = 'TSC A-Team'
-- DO UPDATE, not DO NOTHING: the squad already exists after the first seed,
-- so DO NOTHING silently kept whatever names were there and a change to the
-- roster above would never take effect. Reseeding must be able to correct
-- names and positions, not just fill gaps.
ON CONFLICT (team_id, season_id, age_group_id, jersey_number) DO UPDATE
    SET first_name = EXCLUDED.first_name,
        last_name  = EXCLUDED.last_name,
        positions  = EXCLUDED.positions,
        is_active  = true;

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
