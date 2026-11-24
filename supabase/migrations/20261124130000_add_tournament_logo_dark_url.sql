-- =============================================================================
-- Migration: add logo_dark_url to tournaments (SB-1770)
-- =============================================================================
-- Optional dark-mode variant of the tournament logo. Logos with a black
-- wordmark (e.g. MLS NEXT Flex / Fest) vanish on the dark card ground, so an
-- admin can upload a second image drawn for dark backgrounds.
--
-- NULL = no dark variant; every renderer falls back to logo_url. Uploaded via
-- POST /api/admin/tournaments/{id}/logo?variant=dark into the existing
-- `tournament-logos` bucket as `{id}-dark.{ext}`.
-- =============================================================================

ALTER TABLE public.tournaments
    ADD COLUMN IF NOT EXISTS logo_dark_url TEXT;

COMMENT ON COLUMN public.tournaments.logo_dark_url IS
    'Public URL of the dark-mode tournament logo. NULL = use logo_url in dark mode too.';
