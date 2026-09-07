-- League filter order (SB-1035)
--
-- The League row sorted by name: Academy, Flex, Homegrown, TSC League 1. The
-- competition MT exists for came third. Same shape as match_types.display_order
-- (SB-849): the order lives on the row and the API sorts by it, so the
-- frontend never carries a list of league names.
--
-- NULL sorts last. TSC League 1 and anything added later without an order
-- land after the three that matter, which is where they belong until someone
-- decides otherwise.

ALTER TABLE public.leagues
    ADD COLUMN IF NOT EXISTS display_order integer;

COMMENT ON COLUMN public.leagues.display_order IS
    'Sort position for league filters. Lower first; NULLs sort last.';

UPDATE public.leagues SET display_order = 1 WHERE name = 'Homegrown';
UPDATE public.leagues SET display_order = 2 WHERE name = 'Flex';
UPDATE public.leagues SET display_order = 3 WHERE name = 'Academy';
