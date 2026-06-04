-- =============================================================================
-- Migration: Replace single age_group_id on tournaments with junction table
-- Issue: https://github.com/silverbeer/missing-table/issues/261
--
-- Adds:
--   - tournament_age_groups junction table (many-to-many)
-- Removes:
--   - age_group_id column from tournaments
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Drop the single FK column (no production data to migrate)
-- -----------------------------------------------------------------------------
ALTER TABLE public.tournaments DROP COLUMN IF EXISTS age_group_id;

-- -----------------------------------------------------------------------------
-- Junction table: tournament ↔ age_group (many-to-many)
-- -----------------------------------------------------------------------------
CREATE TABLE public.tournament_age_groups (
    tournament_id INTEGER NOT NULL REFERENCES public.tournaments(id) ON DELETE CASCADE,
    age_group_id  INTEGER NOT NULL REFERENCES public.age_groups(id)  ON DELETE CASCADE,
    PRIMARY KEY (tournament_id, age_group_id)
);

COMMENT ON TABLE public.tournament_age_groups IS 'Maps tournaments to one or more age groups';

-- RLS: public read, admin write
ALTER TABLE public.tournament_age_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tournament_age_groups_public_read"
    ON public.tournament_age_groups FOR SELECT
    USING (true);

CREATE POLICY "tournament_age_groups_admin_write"
    ON public.tournament_age_groups FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'admin'
        )
    );
