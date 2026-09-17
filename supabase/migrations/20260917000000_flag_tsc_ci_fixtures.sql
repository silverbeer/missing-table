-- Put the CI journey fixtures behind is_test (SB-1085)
--
-- quality-journey.yml runs the TSC user-journey suite against production daily
-- and creates a league, division, club, teams and matches prefixed tsc_ci_.
-- None of it was flagged, so real viewers saw CI fixtures in standings and team
-- lists, and the scraper agent was offered tsc_ci_division_1 as a division to go
-- and load (SB-1080 surfaced it in the agent's bootstrap list).
--
-- Only leagues and clubs need the flag: matches_with_test derives is_test from
-- a match's division's league, its tournament, either team's club, or either
-- team's league (SB-591), so the division, both teams and all four matches
-- follow from these two rows.
--
-- Checked in prod on 2026-09-16 before writing this: 4 matches become is_test
-- (prod had 8), no match pairs a tsc_ci team with a real team, and no user
-- profile points at those teams — so nothing real is hidden by this.
--
-- Matched by name rather than id: the ids are prod's, and the next fixture the
-- journey suite leaves behind is flagged by the same rule. Underscores are LIKE
-- wildcards, hence the escapes. Idempotent, and a no-op anywhere the fixtures
-- do not exist (local, CI).
--
-- This is the stopgap. The fixtures should not be there at all — the journey
-- suite's cleanup has been unable to authenticate for weeks (SB-1092) — and
-- content created through the API cannot be marked as test data in the first
-- place (SB-1096).

UPDATE public.leagues
   SET is_test = true
 WHERE name LIKE 'tsc\_ci\_%'
   AND is_test IS DISTINCT FROM true;

UPDATE public.clubs
   SET is_test = true
 WHERE name LIKE 'tsc\_ci\_%'
   AND is_test IS DISTINCT FROM true;
