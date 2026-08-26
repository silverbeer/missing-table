-- Which competitions count toward cup qualification (SB-849)
--
-- League and Flex together are what qualify a team for the cup; friendlies and
-- tournaments do not. For IFA U15 that is 19 League + 6 Flex = 25, and 25 is
-- the number people ask about.
--
-- This lives in the data rather than in the UI on purpose. The alternative —
-- a "League + Flex" special case in the Matches tab — is the same mistake as
-- the hardcoded match-type ids one layer up: the next qualifying competition
-- would mean editing the frontend, the CLI and the standings code separately.
-- Three bugs in two days came from exactly that shape (SB-844, SB-846, and the
-- Matches filter never learning about Flex).
--
-- With the flag here, a new competition is flagged once and every surface
-- agrees: the Matches chips, mt team matches, and the combined standings view.

ALTER TABLE public.match_types
    ADD COLUMN IF NOT EXISTS counts_for_qualification boolean NOT NULL DEFAULT false;

-- Chip/order position. Synthetic chips are placed relative to these:
-- "Qualifying" sits immediately after the flagged types it combines, and
-- "All" sits last.
ALTER TABLE public.match_types
    ADD COLUMN IF NOT EXISTS display_order integer;

COMMENT ON COLUMN public.match_types.counts_for_qualification IS
    'True when matches of this type count toward cup qualification. The "Qualifying" filter is the union of these — never a hardcoded list of names.';
COMMENT ON COLUMN public.match_types.display_order IS
    'Sort position for competition filters. Lower first; NULLs sort last.';

UPDATE public.match_types SET counts_for_qualification = true,  display_order = 1 WHERE name = 'League';
UPDATE public.match_types SET counts_for_qualification = true,  display_order = 2 WHERE name = 'Flex';
UPDATE public.match_types SET counts_for_qualification = false, display_order = 3 WHERE name = 'Tournament';
UPDATE public.match_types SET counts_for_qualification = false, display_order = 4 WHERE name = 'Friendly';

-- Playoff is deliberately NOT flagged. A playoff match is presumed to BE the
-- cup rather than to qualify for it. It has zero matches in every season, so
-- nothing depends on the choice yet, and it is one UPDATE to change once
-- playoffs exist — but it should be a decision someone makes rather than an
-- assumption that hardens silently.
UPDATE public.match_types SET counts_for_qualification = false, display_order = 5 WHERE name = 'Playoff';
