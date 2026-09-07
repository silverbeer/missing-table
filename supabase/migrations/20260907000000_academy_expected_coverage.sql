-- What the Academy Division is supposed to be running (SB-1044)
--
-- SB-1021 gave the coverage report its reference for Homegrown and Flex. It
-- left Academy out, and Academy is the league with the largest gap: MT holds
-- ONE of its twenty conferences — New England — so `mt coverage` answers
--
--     Academy: no expected coverage on file — 1 division(s) present, so this
--     report cannot say whether anything is missing.
--
-- which is the same blind spot SB-1021 was written to close, one league over.
-- Absence produces no row to count, so a conference nobody has ever loaded is
-- indistinguishable from one that does not exist.
--
-- Source: the competition_brackets in the 2026-27 Academy standings feed,
-- mls-next-2-academy-division-26-27, read on 2026-09-07. That is the same
-- document the scraper derives its targets from (SB-1024), so the reference
-- and the collector cannot drift: if MLS Next adds a conference, both learn
-- about it from the same place.

-- === The twenty Academy conferences ========================================
-- Names are the feed's, exactly. missing-table resolves a division by name,
-- and a near miss is not an error — it yields zero matches and a warning
-- (SB-830), which is precisely the silence this table exists to break.
--
-- Mid-Atlantic and Northeast also exist as Homegrown conferences. They are
-- different competitions with different clubs; `divisions` is unique on
-- (name, league_id), which is what keeps the two apart.
--
-- ON CONFLICT keeps production untouched, where New England already exists.
INSERT INTO public.divisions (name, description, league_id)
SELECT v.name, v.description, l.id
FROM (VALUES
    ('Carolinas',                   'MLS NEXT Academy Division - Carolinas Conference'),
    ('Desert',                      'MLS NEXT Academy Division - Desert Conference'),
    ('Garden State',                'MLS NEXT Academy Division - Garden State Conference'),
    ('Great Lakes North',           'MLS NEXT Academy Division - Great Lakes North Conference'),
    ('Great Lakes South',           'MLS NEXT Academy Division - Great Lakes South Conference'),
    ('Heartland',                   'MLS NEXT Academy Division - Heartland Conference'),
    ('Mid-Atlantic',                'MLS NEXT Academy Division - Mid-Atlantic Conference'),
    ('Mountain',                    'MLS NEXT Academy Division - Mountain Conference'),
    ('New England',                 'MLS NEXT Academy Division - New England Conference'),
    ('North',                       'MLS NEXT Academy Division - North Conference'),
    ('Northeast',                   'MLS NEXT Academy Division - Northeast Conference'),
    ('Northern California Coast',   'MLS NEXT Academy Division - Northern California Coast Conference'),
    ('Northern California Redwood', 'MLS NEXT Academy Division - Northern California Redwood Conference'),
    ('Pacific Northwest',           'MLS NEXT Academy Division - Pacific Northwest Conference'),
    ('Pioneer',                     'MLS NEXT Academy Division - Pioneer Conference'),
    ('South',                       'MLS NEXT Academy Division - South Conference'),
    ('Southern California',         'MLS NEXT Academy Division - Southern California Conference'),
    ('Sunshine North',              'MLS NEXT Academy Division - Sunshine North Conference'),
    ('Sunshine South',              'MLS NEXT Academy Division - Sunshine South Conference'),
    ('Virginia',                    'MLS NEXT Academy Division - Virginia Conference')
) AS v(name, description)
CROSS JOIN public.leagues l
WHERE l.name = 'Academy'
ON CONFLICT (name, league_id) DO NOTHING;

-- === Expected coverage, 2026-27 ============================================
-- Every Academy conference runs all six age groups: the feed declares 120
-- brackets, 20 conferences x U13, U14, U15, U16, U17, U19, with no gaps. That
-- is unlike Homegrown, whose Pathway brackets start at U16, and unlike Flex,
-- which has no U13 or U14 at all — so this is stated as its own insert rather
-- than folded into either of theirs.
--
-- Season and age groups are matched by name, not id: ids differ between local,
-- CI and production, and a migration that hardcodes them seeds the wrong
-- season somewhere without saying so.
INSERT INTO public.division_age_groups (division_id, age_group_id, season_id)
SELECT d.id, ag.id, s.id
FROM public.divisions d
JOIN public.leagues l ON l.id = d.league_id AND l.name = 'Academy'
CROSS JOIN public.age_groups ag
CROSS JOIN public.seasons s
WHERE s.name = '2026-2027'
  AND ag.name IN ('U13', 'U14', 'U15', 'U16', 'U17', 'U19')
ON CONFLICT ON CONSTRAINT division_age_groups_unique DO NOTHING;
