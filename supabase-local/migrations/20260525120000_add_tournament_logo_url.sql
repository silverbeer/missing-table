-- =============================================================================
-- Migration: add logo_url to tournaments + create tournament-logos bucket
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
    'Public URL of the tournament logo (Supabase Storage). NULL = no logo set; UI falls back to text-only rendering.';

-- ─── Storage bucket (IaC, was previously done by hand via Studio UI) ─────────
-- Public bucket so the served URLs don't require signed-URL TTLs. 2MB cap +
-- mime allowlist matches the API endpoint's runtime validation (defense in
-- depth, not strictly required for correctness). Idempotent — safe to re-apply.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'tournament-logos',
    'tournament-logos',
    true,
    2097152,                                  -- 2 MiB
    ARRAY['image/png', 'image/jpeg', 'image/jpg']
)
ON CONFLICT (id) DO NOTHING;
