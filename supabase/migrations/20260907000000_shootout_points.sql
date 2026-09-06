-- Which competitions settle a level match on penalties, and score it (SB-1027)
--
-- MLS NEXT Flex has no draws at U15-U19. A match level after regulation goes
-- straight to a shootout, and the shootout is worth points: winner 2, loser 1.
-- A regulation win is still 3. Confirmed against the official 2026 MLS NEXT
-- Flex group tables (modular11, embedded on mlssoccer.com), which reconcile
-- with the match list only under that model — e.g. U17 Group C: Orlando City
-- 2W + 1 shootout win = 8, NEFC 2W + 1 shootout loss = 7.
--
-- Homegrown League play is the opposite: a draw is a draw, 1 point each, per
-- the 2026-27 Allstate Homegrown Division Rules and Regulations (section k,
-- Standings: Win 3 / Tie 1 / Loss 0). Production agrees — 216 level League
-- matches, not one with a shootout recorded.
--
-- Tournament shootouts are knockout progression, not table points, and must
-- not be scored this way either. So this is a property of the competition,
-- not of the match: a match with penalty scores recorded earns shootout points
-- only when its match type says so. Same shape as counts_for_qualification —
-- one flag on one row, read by the standings code, never a list of names.

ALTER TABLE public.match_types
    ADD COLUMN IF NOT EXISTS shootout_points boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.match_types.shootout_points IS
    'True when a match level after regulation is settled on penalties and the shootout is worth table points: winner 2, loser 1 (MLS NEXT Flex). False means a draw is a draw, 1 point each.';

UPDATE public.match_types SET shootout_points = true WHERE name = 'Flex';
