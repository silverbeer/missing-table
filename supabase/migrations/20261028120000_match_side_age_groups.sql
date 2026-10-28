-- SB-1444: per-side age group, for matches where one team plays up.
--
-- A match has one age_group_id. When IFA U15 plays the New England Revolution
-- U16 in a friendly, the match is U15 and the Revolution's side is U16 -- and
-- with only the match-level column, that match never appears under the
-- Revolution's U16 team.
--
-- NULL means "same as the match's age group", which is every scraped match
-- and almost every manual one. Nothing that writes matches has to change;
-- only a playing-up side is ever set.

-- Deliberately NO foreign key to age_groups. A second and third FK from
-- matches to age_groups makes every existing `age_group:age_groups(...)` embed
-- ambiguous (PostgREST PGRST201, "more than one relationship was found"), and
-- that embed is on every match read path in the backend and the scraper.
-- Only the match forms set these, from the /api/age-groups list; the scraper
-- never does.
ALTER TABLE public.matches
    ADD COLUMN IF NOT EXISTS home_age_group_id INTEGER,
    ADD COLUMN IF NOT EXISTS away_age_group_id INTEGER;

COMMENT ON COLUMN public.matches.home_age_group_id IS
    'Age group the home side fielded, when it differs from age_group_id '
    '(playing up/down, SB-1444). NULL = same as age_group_id.';
COMMENT ON COLUMN public.matches.away_age_group_id IS
    'Age group the away side fielded, when it differs from age_group_id '
    '(playing up/down, SB-1444). NULL = same as age_group_id.';

-- matches_with_test froze its column list at creation (SELECT m.* is expanded
-- once), so the new columns are invisible to the read path until the view is
-- rebuilt. Same definition as 20260829000000_scoring_mode.sql.
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
