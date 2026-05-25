-- =============================================================================
-- Migration: add logo_url to tournaments
-- =============================================================================
-- Optional logo (small shield / mark) per tournament. Shown on the public
-- tournament page header and on IG share cards when set. Falls back to the
-- existing "no logo" rendering when null, so legacy tournaments stay valid.
-- Uploaded via POST /api/admin/tournaments/{id}/logo (multipart → Supabase
-- Storage `tournament-logos` bucket) — mirrors the club-logo flow.
-- =============================================================================

ALTER TABLE public.tournaments
    ADD COLUMN IF NOT EXISTS logo_url TEXT;

COMMENT ON COLUMN public.tournaments.logo_url IS
    'Public URL of the tournament logo (Supabase Storage / R2). NULL = no logo set; UI falls back to text-only rendering.';
