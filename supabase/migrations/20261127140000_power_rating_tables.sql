-- SB-1807: MT Power Rating storage (design: docs/03-architecture/power-rating.md,
-- "Data model"). The engine is pure (backend/mt_tools/power_rating.py); these
-- tables only store what a run published.
--
--   power_rating_runs          one per (season, age group, league) per run that
--                              changed something: a run whose input fingerprint
--                              matches the latest run writes nothing
--   power_ratings              one per rated team per run
--   power_rating_match_deltas  two per rated match, LATEST RUN ONLY: older runs'
--                              deltas are deleted when a new run is written
--
-- Run `./scripts/db_tools.sh migrate prod` BEFORE deploying the code: the
-- nightly job and POST /api/admin/power-rating/recompute write to these tables.
--
-- Backups (SB-1071): runs and ratings are backed up (the record of what MT
-- published about minors' teams; not reproducible once the parameters change).
-- Deltas are excluded: derived, rebuilt on every run. No user FKs.
--
-- RLS: logged-in users may read; only the backend (service role) writes.

CREATE TABLE IF NOT EXISTS public.power_rating_runs (
    id bigserial PRIMARY KEY,
    season_id integer NOT NULL REFERENCES public.seasons(id) ON DELETE CASCADE,
    age_group_id integer NOT NULL REFERENCES public.age_groups(id) ON DELETE CASCADE,
    league_id integer NOT NULL REFERENCES public.leagues(id) ON DELETE CASCADE,
    computed_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    through_date date,
    params jsonb NOT NULL DEFAULT '{}'::jsonb,
    params_version text NOT NULL,
    input_fingerprint text NOT NULL,
    matches_counted integer NOT NULL DEFAULT 0 CHECK (matches_counted >= 0),
    matches_excluded jsonb NOT NULL DEFAULT '{}'::jsonb,
    national boolean NOT NULL DEFAULT false,
    publication_reason text
);

COMMENT ON TABLE public.power_rating_runs IS 'One MT Power Rating run for a season, age group and league (SB-1807).';
COMMENT ON COLUMN public.power_rating_runs.through_date IS 'Date of the latest rated match; NULL when nothing was rated.';
COMMENT ON COLUMN public.power_rating_runs.input_fingerprint IS 'sha256 of the engine input (match ids, scores, status, pool flags) and params_version; unchanged means the run is skipped.';
COMMENT ON COLUMN public.power_rating_runs.matches_excluded IS 'Matches read but not rated, by reason: forfeit, out_of_pool_opponent, other_age_group, no_score.';
COMMENT ON COLUMN public.power_rating_runs.publication_reason IS 'Why there is no national list; NULL when national.';

CREATE INDEX IF NOT EXISTS idx_power_rating_runs_scope
    ON public.power_rating_runs (season_id, age_group_id, league_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS public.power_ratings (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES public.power_rating_runs(id) ON DELETE CASCADE,
    team_id integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    rating double precision NOT NULL,
    start_rating double precision NOT NULL,
    rank integer CHECK (rank >= 1),
    island integer NOT NULL,
    conference_division_id integer REFERENCES public.divisions(id) ON DELETE SET NULL,
    conference_rank integer CHECK (conference_rank >= 1),
    mp integer NOT NULL CHECK (mp >= 0),
    w integer NOT NULL CHECK (w >= 0),
    d integer NOT NULL CHECK (d >= 0),
    l integer NOT NULL CHECK (l >= 0),
    xconf_mp integer NOT NULL CHECK (xconf_mp >= 0),
    sos double precision,
    tier text,
    badges text[] NOT NULL DEFAULT '{}'::text[],
    massey_rank integer CHECK (massey_rank >= 1),
    CONSTRAINT uq_power_ratings_run_team UNIQUE (run_id, team_id)
);

COMMENT ON TABLE public.power_ratings IS 'One team''s MT Power Rating in one run (SB-1807).';
COMMENT ON COLUMN public.power_ratings.rank IS 'National rank. NULL when unranked (under 6 rated matches), outside the main island, or the age group has no national list.';
COMMENT ON COLUMN public.power_ratings.conference_rank IS 'Rank among ranked teams of the same conference. NULL when unranked or without a conference.';
COMMENT ON COLUMN public.power_ratings.sos IS 'Mean opponent rating before each rated match.';
COMMENT ON COLUMN public.power_ratings.massey_rank IS 'Massey audit rank within the team''s island, ranked teams only.';

CREATE INDEX IF NOT EXISTS idx_power_ratings_team ON public.power_ratings (team_id, run_id);

CREATE TABLE IF NOT EXISTS public.power_rating_match_deltas (
    id bigserial PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES public.power_rating_runs(id) ON DELETE CASCADE,
    match_id integer NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    team_id integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    opponent_id integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    rating_before double precision NOT NULL,
    opponent_before double precision NOT NULL,
    expected double precision NOT NULL,
    result double precision NOT NULL,
    k double precision NOT NULL,
    margin_mult double precision NOT NULL,
    delta double precision NOT NULL,
    CONSTRAINT uq_power_rating_match_deltas_run_match_team UNIQUE (run_id, match_id, team_id)
);

COMMENT ON TABLE public.power_rating_match_deltas IS 'Per-match rating changes of the latest run only; derived, rebuilt every run (SB-1807).';

CREATE INDEX IF NOT EXISTS idx_power_rating_match_deltas_team
    ON public.power_rating_match_deltas (run_id, team_id);

ALTER TABLE public.power_rating_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.power_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.power_rating_match_deltas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS power_rating_runs_authenticated_read ON public.power_rating_runs;
CREATE POLICY power_rating_runs_authenticated_read
    ON public.power_rating_runs
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS power_ratings_authenticated_read ON public.power_ratings;
CREATE POLICY power_ratings_authenticated_read
    ON public.power_ratings
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS power_rating_match_deltas_authenticated_read ON public.power_rating_match_deltas;
CREATE POLICY power_rating_match_deltas_authenticated_read
    ON public.power_rating_match_deltas
    FOR SELECT
    TO authenticated
    USING (true);

GRANT SELECT ON public.power_rating_runs, public.power_ratings, public.power_rating_match_deltas TO authenticated;
GRANT ALL ON public.power_rating_runs, public.power_ratings, public.power_rating_match_deltas TO service_role;
GRANT USAGE, SELECT ON SEQUENCE
    public.power_rating_runs_id_seq,
    public.power_ratings_id_seq,
    public.power_rating_match_deltas_id_seq
    TO service_role;
