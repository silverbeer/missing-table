-- =============================================================================
-- Migration: add tournament_round_order to matches
-- =============================================================================
-- Bracket cells in MT are placed in a vertical column. When matches are
-- loaded into the DB in an order that doesn't match the canonical bracket
-- top-to-bottom layout, sorting by `id` gives the wrong vertical positions
-- and the connector lines from R32 -> R16 -> QF -> SF -> Final point at
-- the wrong feeders.
--
-- `tournament_round_order` is the explicit bracket-position field. 0-based,
-- top of the bracket = 0. Frontend prefers this when present and falls
-- back to id when null, so older tournaments still render correctly.
-- =============================================================================

ALTER TABLE public.matches
    ADD COLUMN IF NOT EXISTS tournament_round_order INTEGER;

COMMENT ON COLUMN public.matches.tournament_round_order IS
    'Bracket position within a tournament round (0-based; top of bracket = 0). Used for stable bracket-display ordering when match ids do not match the canonical bracket order. Null is fine — frontend falls back to id-order for legacy rows.';

-- Partial index: only tournament matches need fast slot lookup, and only
-- when the field is set. Keeps the index small.
CREATE INDEX IF NOT EXISTS idx_matches_tournament_round_order
    ON public.matches (tournament_id, tournament_round, tournament_round_order)
    WHERE tournament_id IS NOT NULL AND tournament_round_order IS NOT NULL;
