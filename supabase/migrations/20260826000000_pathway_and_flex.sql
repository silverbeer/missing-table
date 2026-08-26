-- 2026-2027 competition structure: Pro Player Pathway and MLS NEXT Flex (SB-833)
--
-- Reference data only. No schema change, no behaviour change — these are the
-- rows the scrape and the standings views depend on.
--
-- Everything here was verified against the live Kitman feeds on 2026-08-25:
--   https://mls-assist.theintelligenceplatform.com/data/standings/<key>.json
--
-- Two competitions are new to MT, and they are new in DIFFERENT WAYS. Getting
-- that distinction wrong is the expensive mistake, so it is spelled out:
--
--   Pro Player Pathway is a DIVISION, not a competition. Its brackets sit
--   inside the same mls-next-league-26-27 feed as the geographic conferences,
--   and League fixtures stay inside their bracket (7,640 in-bracket vs 8
--   cross). A Pathway team's matches ARE League matches; they simply belong to
--   a different table. It therefore needs divisions and NO match type — making
--   it a match type would move ~29 pro academies' League records out of
--   League, so `mt team stats <club>` (which defaults to -c League) would
--   return nothing for any of them.
--
--   MLS NEXT Flex is a COMPETITION played by the same teams. 563 of its 567
--   squads also appear in the League feed and none appear in Academy, matching
--   "non-academy teams play 6 Flex + 19 League"; combined fixtures per squad
--   cluster at 25-26. It needs BOTH a match type (so Flex goals do not land in
--   the League Golden Boot, which resolves competition to a match_type) and
--   its own divisions (so Flex standings group by Flex bracket, not by the
--   team's Homegrown division).

-- === Flex as a match type ==================================================
-- The competition axis. `mt team stats -c` and the Golden Boot both resolve a
-- competition name to a match_types row, so without this every Flex goal would
-- be counted as a League goal and GP would read 25 instead of 19.
INSERT INTO public.match_types (name)
VALUES ('Flex')
ON CONFLICT (name) DO NOTHING;

-- === Flex as a league ======================================================
-- Used as the namespace for Flex divisions, not as a statement about team
-- membership: teams keep their Homegrown teams.league_id. It is needed because
-- `divisions` is UNIQUE (name, league_id) and the Flex bracket names collide
-- with Homegrown ones — Florida, Frontier, Northwest and Southeast are each a
-- Homegrown division AND a separate Flex one.
--
-- Consistent with existing usage: `leagues` already holds competitions
-- (Homegrown = "MLS Next Top League", Academy = "MLS Next League 2").
--
-- The name matches what match-scraper sends as `league` (its LEAGUE_FEEDS key),
-- so MT's league-scoped division lookup resolves it (SB-830).
INSERT INTO public.leagues (name, description, is_active, sport_type)
VALUES ('Flex', 'MLS NEXT Flex', true, 'soccer')
ON CONFLICT (name) DO NOTHING;

-- === Pro Player Pathway divisions ==========================================
-- Under Homegrown (league_id 1), U16/U17/U19 only — there is no U15 Pathway
-- bracket in any feed, because 29 of the 30 Pathway clubs field no U15 team at
-- all (their U15 cohort plays up into U16). Real Salt Lake is the exception.
--
-- Pathway geography is its OWN: Central/Northeast/Southeast/West, which is not
-- the eight-conference Homegrown map. So these are genuinely distinct rows, not
-- a flag on the existing divisions.
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.descr, 1
FROM (VALUES
    ('Central (Pro Player Pathway)',   'MLS Next Pro Player Pathway — Central'),
    ('Northeast (Pro Player Pathway)', 'MLS Next Pro Player Pathway — Northeast'),
    ('Southeast (Pro Player Pathway)', 'MLS Next Pro Player Pathway — Southeast'),
    ('West (Pro Player Pathway)',      'MLS Next Pro Player Pathway — West')
) AS v(name, descr)
ON CONFLICT (name, league_id) DO NOTHING;

-- === MLS NEXT Flex divisions ===============================================
-- The 13 Flex conference brackets, U15/U16/U17/U19 (no U13/U14 — those age
-- groups play no Flex at all). Note these do NOT partition the Homegrown
-- divisions: 31 of 52 Flex brackets draw from more than one Homegrown region
-- even after folding Pathway into its parent, which is why a combined
-- "all competitions" table is a record rather than a standing (SB-834).
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.descr, l.id
FROM (VALUES
    ('Empire',             'MLS NEXT Flex — Empire'),
    ('Florida',            'MLS NEXT Flex — Florida'),
    ('Frontier',           'MLS NEXT Flex — Frontier'),
    ('Mid-America (East)', 'MLS NEXT Flex — Mid-America East'),
    ('Mid-America (West)', 'MLS NEXT Flex — Mid-America West'),
    ('Mid-Atlantic (North)', 'MLS NEXT Flex — Mid-Atlantic North'),
    ('Mid-Atlantic (South)', 'MLS NEXT Flex — Mid-Atlantic South'),
    ('New England',        'MLS NEXT Flex — New England'),
    ('Northwest',          'MLS NEXT Flex — Northwest'),
    ('Southeast',          'MLS NEXT Flex — Southeast'),
    ('Southwest (North)',  'MLS NEXT Flex — Southwest North'),
    ('Southwest (South)',  'MLS NEXT Flex — Southwest South'),
    ('Turnpike',           'MLS NEXT Flex — Turnpike')
) AS v(name, descr)
CROSS JOIN (SELECT id FROM public.leagues WHERE name = 'Flex') AS l
ON CONFLICT (name, league_id) DO NOTHING;
