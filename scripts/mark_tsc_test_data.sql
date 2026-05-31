-- Tag the TSC test world as is_test (SB-85, Phase 1).
--
-- Re-runnable / idempotent. Run on local after the is_test migration, and on
-- prod as a deploy step (like a migration):
--   local: psql "$LOCAL_DB_URL" -f scripts/mark_tsc_test_data.sql
--   prod:  psql "$PROD_DB_URL"  -f scripts/mark_tsc_test_data.sql
--
-- Identifies the TSC world by name/username rather than hard-coded ids so it
-- works across environments (local ids differ from prod). Prod ids for
-- reference: league 90, club 93, tournament 7.

UPDATE public.leagues       SET is_test = true WHERE name = 'TSC League 1';
UPDATE public.tournaments   SET is_test = true WHERE name = 'TSC Bracket Test Cup';
UPDATE public.user_profiles SET is_test = true WHERE username LIKE 'tsc\_%';

-- Clubs: derive from test-league membership rather than matching the club name.
-- The TSC club is "Toms Soccer Club" (TSC = initials, name spelled out), so a
-- name match like ILIKE 'TSC%' misses it. Any club fielding a team in a test
-- league is itself test. Run the leagues UPDATE above first so is_test is set.
UPDATE public.clubs SET is_test = true
WHERE id IN (
    SELECT DISTINCT t.club_id
    FROM public.teams t
    JOIN public.leagues l ON l.id = t.league_id
    WHERE l.is_test AND t.club_id IS NOT NULL
);

-- Report what is now flagged.
SELECT 'leagues'       AS entity, count(*) FILTER (WHERE is_test) AS test_rows FROM public.leagues
UNION ALL SELECT 'clubs',         count(*) FILTER (WHERE is_test) FROM public.clubs
UNION ALL SELECT 'tournaments',   count(*) FILTER (WHERE is_test) FROM public.tournaments
UNION ALL SELECT 'user_profiles', count(*) FILTER (WHERE is_test) FROM public.user_profiles;
