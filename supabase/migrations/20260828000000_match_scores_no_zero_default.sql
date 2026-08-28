-- SB-886: a match nobody has played must have no score, not a 0-0 draw.
--
-- Production drifted from the tracked baseline: `matches.home_score` and
-- `away_score` carry `DEFAULT 0` in prod, while
-- supabase/migrations/00000000000000_schema.sql:957 declares them as bare
-- `integer` with no default. Any insert that omitted a score therefore stored
-- a nil-nil draw in prod and a NULL locally -- which is why the Tournaments tab
-- shows "0 - 0" on fixtures that kick off tomorrow, and why it never
-- reproduced in local development.
--
-- The penalty columns were always correct (no default, NULL when unplayed);
-- this brings the score columns in line with them.
--
-- Both statements are no-ops on a database already built from the baseline,
-- so this is safe to apply anywhere.

-- 1. Stop manufacturing the zeros.
ALTER TABLE public.matches ALTER COLUMN home_score DROP DEFAULT;
ALTER TABLE public.matches ALTER COLUMN away_score DROP DEFAULT;

-- 2. Clear the ones already stored.
--
-- Scoped to statuses that mean "no result exists": scheduled, tbd, cancelled.
-- `completed` is deliberately excluded -- it holds 42 genuine 0-0 draws, and a
-- broader predicate would erase them. `in_progress` and `forfeit` are excluded
-- for the same reason: a live match at 0-0 is a real scoreline.
UPDATE public.matches
   SET home_score = NULL,
       away_score = NULL
 WHERE match_status IN ('scheduled', 'tbd', 'cancelled')
   AND home_score = 0
   AND away_score = 0;

COMMENT ON COLUMN public.matches.home_score IS
  'Goals scored by the home team. NULL until a result exists -- never 0 as a placeholder (see SB-886).';
COMMENT ON COLUMN public.matches.away_score IS
  'Goals scored by the away team. NULL until a result exists -- never 0 as a placeholder (see SB-886).';
