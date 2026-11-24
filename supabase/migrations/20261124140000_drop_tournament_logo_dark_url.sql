-- =============================================================================
-- Migration: drop tournaments.logo_dark_url (SB-1771, rolls back SB-1770)
-- =============================================================================
-- The dark-mode logo variant is withdrawn. The tournament logo slot is a small
-- square, where only a compact crest reads, and crests work on light and dark
-- grounds alike; share cards already plate a too-dark logo (SB-901). Admins
-- are asked for a square, transparent, shield-only logo instead.
--
-- Run `migrate prod` only AFTER the SB-1771 code is deployed: the SB-1770 code
-- selects this column, and dropping it first would fail every tournament read.
-- =============================================================================

ALTER TABLE public.tournaments
    DROP COLUMN IF EXISTS logo_dark_url;
