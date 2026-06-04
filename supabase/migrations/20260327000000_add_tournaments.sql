-- =============================================================================
-- Migration: Add tournament tracking
-- Issue: https://github.com/silverbeer/missing-table/issues/261
--
-- Adds:
--   - tournaments table
--   - tournament_id, tournament_group, tournament_round columns on matches
-- =============================================================================

-- -----------------------------------------------------------------------------
-- tournaments table
-- -----------------------------------------------------------------------------
CREATE TABLE public.tournaments (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE,
    location     TEXT,
    description  TEXT,
    age_group_id INTEGER REFERENCES public.age_groups(id) ON DELETE SET NULL,
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.tournaments                IS 'Named tournaments (e.g. Generation adidas Cup 2026)';
COMMENT ON COLUMN public.tournaments.age_group_id   IS 'Primary age group for the tournament; NULL if multi-age';
COMMENT ON COLUMN public.tournaments.is_active       IS 'Controls visibility on public-facing views';

-- RLS: public read, admin write
ALTER TABLE public.tournaments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tournaments_public_read"
    ON public.tournaments FOR SELECT
    USING (true);

CREATE POLICY "tournaments_admin_write"
    ON public.tournaments FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'admin'
        )
    );

-- -----------------------------------------------------------------------------
-- Add tournament context columns to matches
-- -----------------------------------------------------------------------------
ALTER TABLE public.matches
    ADD COLUMN tournament_id    INTEGER REFERENCES public.tournaments(id) ON DELETE SET NULL,
    ADD COLUMN tournament_group TEXT,
    ADD COLUMN tournament_round TEXT;

COMMENT ON COLUMN public.matches.tournament_id    IS 'Links match to a tournament; NULL for regular league matches';
COMMENT ON COLUMN public.matches.tournament_group IS 'Group name within the tournament (e.g. ''Group A'')';
COMMENT ON COLUMN public.matches.tournament_round IS 'Round within the tournament (e.g. ''group_stage'', ''quarterfinal'', ''semifinal'', ''final'')';

CREATE INDEX idx_matches_tournament_id ON public.matches(tournament_id)
    WHERE tournament_id IS NOT NULL;

CREATE TRIGGER tournaments_updated_at
    BEFORE UPDATE ON public.tournaments
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
