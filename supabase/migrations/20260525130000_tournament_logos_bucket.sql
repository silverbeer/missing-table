-- =============================================================================
-- Migration: create the `tournament-logos` Supabase Storage bucket
-- =============================================================================
-- This is a follow-up to 20260525120000_add_tournament_logo_url.sql. The
-- original migration also included this INSERT, but it was dropped during
-- the squash-merge of PR #398, leaving new environments without the bucket
-- (prod was patched manually via Studio).
--
-- Idempotent (ON CONFLICT DO NOTHING) — safe to apply against environments
-- where the bucket already exists.
-- =============================================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'tournament-logos',
    'tournament-logos',
    true,
    2097152,                                  -- 2 MiB
    ARRAY['image/png', 'image/jpeg', 'image/jpg']
)
ON CONFLICT (id) DO NOTHING;
