-- Prod test partition (SB-85, Phase 1).
--
-- Adds an is_test flag to the top-level entities so a self-contained test world
-- (the TSC league/clubs/teams/tournaments + tsc_* users) can be hidden from real
-- users while staying visible to test users and admins.
--
-- Visibility rule (enforced in the API, not the DB): a viewer sees test content
-- iff viewer.is_test OR viewer.role = 'admin'. Default false → real data and real
-- users are completely unaffected.
--
-- Phase 1 filters the two list endpoints (/api/tournaments, /api/leagues). The
-- columns on clubs is for Phase 2 (matches/search) but added now so tagging is
-- done once.

ALTER TABLE public.leagues       ADD COLUMN is_test boolean NOT NULL DEFAULT false;
ALTER TABLE public.clubs         ADD COLUMN is_test boolean NOT NULL DEFAULT false;
ALTER TABLE public.tournaments   ADD COLUMN is_test boolean NOT NULL DEFAULT false;
ALTER TABLE public.user_profiles ADD COLUMN is_test boolean NOT NULL DEFAULT false;

-- Partial indexes: the filtered queries only ever care about the (small) test set
-- or exclude it; a partial index on the rare true rows keeps it cheap.
CREATE INDEX idx_tournaments_is_test ON public.tournaments(is_test) WHERE is_test;
CREATE INDEX idx_leagues_is_test     ON public.leagues(is_test)     WHERE is_test;

COMMENT ON COLUMN public.tournaments.is_test IS
    'Test-only tournament; hidden from non-test, non-admin viewers (SB-85).';
COMMENT ON COLUMN public.leagues.is_test IS
    'Test-only league; hidden from non-test, non-admin viewers (SB-85).';
COMMENT ON COLUMN public.user_profiles.is_test IS
    'Test user; may see is_test content (SB-85).';
