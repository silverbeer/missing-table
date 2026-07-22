-- Admin-settable current season (SB: current-season flag)
--
-- "Current season" was derived from start_date <= today <= end_date in three
-- separate places, which returns nothing during the off-season gap (e.g. a
-- July date between two seasons) and silently defaulted UIs to hardcoded
-- season names. Replace with an explicit admin-controlled flag.

ALTER TABLE public.seasons
    ADD COLUMN IF NOT EXISTS is_current boolean NOT NULL DEFAULT false;

-- At most one current season. Partial unique index over the TRUE value only;
-- any number of rows may be false.
CREATE UNIQUE INDEX IF NOT EXISTS seasons_single_current
    ON public.seasons (is_current)
    WHERE is_current;

COMMENT ON COLUMN public.seasons.is_current IS
    'Admin-set current season. Exactly one row is true (partial unique index). Season dropdowns default to it.';

-- Backfill: pick the sensible current season if none is flagged yet.
-- Priority: the season spanning today, else the earliest still-ongoing/upcoming
-- season (end_date >= today), else the newest by start_date.
UPDATE public.seasons
SET is_current = true, updated_at = CURRENT_TIMESTAMP
WHERE id = (
    SELECT id
    FROM public.seasons
    ORDER BY
        (start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE) DESC,
        (end_date >= CURRENT_DATE) DESC,
        start_date ASC,
        id ASC
    LIMIT 1
)
AND NOT EXISTS (SELECT 1 FROM public.seasons WHERE is_current);
