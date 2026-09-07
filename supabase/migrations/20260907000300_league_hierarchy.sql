-- League hierarchy: a competition's conferences live under their division (SB-1039)
--
-- The official MLS NEXT standings are organised Division (Homegrown, Academy)
-- → tab (League, MLS NEXT Flex) → Conference. MT modelled Flex as a third
-- league beside Homegrown and Academy, because the scraper names it as a
-- competition and ingest resolves competition names to leagues (SB-852).
-- That stays: nothing in ingest changes. What changes is that a league can
-- now say which league it belongs to, and which competition its conferences
-- are the tables of.
--
--   parent_league_id  Flex → Homegrown. A league with a parent is not a
--                     division of its own; it is one of its parent's tabs.
--   match_type_id     Homegrown, Academy → League; Flex → Flex. The
--                     competition whose tables this league's conferences are.
--                     Lets "Homegrown + Flex" resolve to the 13 Flex
--                     conferences without a name lookup.
--
-- Pro Player Pathway needs nothing here: the official League tab lists its
-- tables as conferences ("Northeast (Pro Player Pathway) Conference"), which
-- is how MT already holds them.

ALTER TABLE public.leagues
    ADD COLUMN IF NOT EXISTS parent_league_id integer REFERENCES public.leagues(id),
    ADD COLUMN IF NOT EXISTS match_type_id integer REFERENCES public.match_types(id);

COMMENT ON COLUMN public.leagues.parent_league_id IS
    'The division this league is a competition of (Flex → Homegrown). NULL for a top-level division.';
COMMENT ON COLUMN public.leagues.match_type_id IS
    'The competition whose tables this league''s conferences are (League for Homegrown/Academy, Flex for Flex).';

UPDATE public.leagues SET match_type_id = (SELECT id FROM public.match_types WHERE name = 'League')
    WHERE name IN ('Homegrown', 'Academy');
UPDATE public.leagues
    SET parent_league_id = (SELECT id FROM public.leagues WHERE name = 'Homegrown'),
        match_type_id = (SELECT id FROM public.match_types WHERE name = 'Flex')
    WHERE name = 'Flex';
