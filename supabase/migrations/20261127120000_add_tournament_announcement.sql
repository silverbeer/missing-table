-- =============================================================================
-- Migration: add announcement to tournaments (SB-1797)
-- =============================================================================
-- Optional admin-set announcement for a tournament, shown on its card in the
-- Tournaments index and in the hero status ribbon, and the reason the
-- Tournaments tab shows a "new" dot. First use: "Every MLS NEXT Fest match
-- scored live."
--
-- NULL = no announcement; every renderer shows nothing. Short by design: it is
-- one line on a phone.
--
-- Run `migrate prod` BEFORE the SB-1797 code deploys: that code selects this
-- column, and every tournament read fails without it.
-- =============================================================================

ALTER TABLE public.tournaments
    ADD COLUMN IF NOT EXISTS announcement TEXT
    CHECK (announcement IS NULL OR char_length(announcement) BETWEEN 1 AND 160);

COMMENT ON COLUMN public.tournaments.announcement IS
    'One-line announcement shown on the tournament card and hero ribbon. NULL = none.';
