-- SB-910: separate "the match is under way" from "someone is live-scoring it".
--
-- Setting a match live meant two different things at once: the ball is rolling,
-- and a manager is driving the live-scoring clock with goal events. Most
-- matches are the first without the second -- a parent marks the match in
-- progress and types the score their partner texted them from the touchline.
-- Those matches then appeared on the LIVE tab with nobody driving them.
--
-- The fix is NOT a second status value. "live" and "in progress" are the same
-- match state, and splitting the enum would fragment every check that keys on
-- it (stats' PLAYED_STATUSES, the playoff advance guard, idx_matches_live_status,
-- the standings queries, the CLI, eight frontend branches) -- miss one and a
-- match silently stops counting.
--
-- So: one status axis, plus an explicit scoring mode. match_status stays
-- scheduled -> live -> completed and every existing query keeps working.
-- scoring_mode says how the score gets in, which is a provenance question and
-- belongs in its own column (CLAUDE.md: provenance is queryable).

ALTER TABLE public.matches
    ADD COLUMN IF NOT EXISTS scoring_mode text NOT NULL DEFAULT 'manual';

ALTER TABLE public.matches
    DROP CONSTRAINT IF EXISTS matches_scoring_mode_check;

ALTER TABLE public.matches
    ADD CONSTRAINT matches_scoring_mode_check
    CHECK (scoring_mode IN ('manual', 'live'));

COMMENT ON COLUMN public.matches.scoring_mode IS
  'How this match''s score is being recorded: ''live'' once live scoring has '
  'started (the clock ran), ''manual'' otherwise. Orthogonal to match_status, '
  'which says what state the match is in (SB-910).';

-- Backfill from the clock. kickoff_time is only ever written by the
-- start_first_half clock action, so a match that has one was live-scored.
UPDATE public.matches
   SET scoring_mode = 'live'
 WHERE kickoff_time IS NOT NULL
   AND scoring_mode <> 'live';

-- The LIVE tab's query: live AND live-scored.
DROP INDEX IF EXISTS public.idx_matches_live_scored;
CREATE INDEX idx_matches_live_scored
    ON public.matches (match_status)
    WHERE match_status = 'live'::public.match_status AND scoring_mode = 'live';

-- matches_with_test froze its column list at creation (SELECT m.* is expanded
-- once), so a new column on matches is invisible to the read path until the
-- view is rebuilt. CREATE OR REPLACE cannot do it -- the new column lands
-- before is_test, not at the end -- so drop and recreate, then re-grant.
DROP VIEW IF EXISTS public.matches_with_test;

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

GRANT SELECT ON public.matches_with_test TO anon, authenticated, service_role;
