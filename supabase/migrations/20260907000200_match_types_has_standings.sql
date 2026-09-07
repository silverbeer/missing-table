-- Which competitions produce a standings table (SB-1037)
--
-- The Table tab offered Tournament and Friendly. Neither is a standing: a
-- friendly table is nonsense, and a tournament table across every tournament
-- in a division is meaningless — tournaments have their own group tables and
-- brackets under the Tournaments tab. Playoff is a bracket, not a table.
--
-- One row, one flag, like counts_for_qualification and shootout_points. The
-- Table's competition row offers only flagged competitions; the Matches tab
-- is unchanged, because a schedule that hides friendlies is the surprise.

ALTER TABLE public.match_types
    ADD COLUMN IF NOT EXISTS has_standings boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.match_types.has_standings IS
    'True when matches of this type produce a league table. The Table tab offers only these; the Matches tab offers every type.';

UPDATE public.match_types SET has_standings = true WHERE name IN ('League', 'Flex');
