-- SB-260: Tie tournaments to a season.
--
-- Tournaments were season-agnostic; the Tournaments view now defaults to the
-- current (newest) season and lets users switch back to prior seasons. This
-- adds a season_id FK to tournaments, backfills existing rows to 2025-2026,
-- and seeds the 2026-2027 season so it can become the new default.

-- 1. Ensure the 2026-2027 season exists (idempotent; name is UNIQUE).
INSERT INTO public.seasons (name, start_date, end_date)
VALUES ('2026-2027', '2026-09-01', '2027-06-30')
ON CONFLICT (name) DO NOTHING;

-- 2. Add the season_id column (nullable for now so the backfill can run).
--    ON DELETE RESTRICT: deleting a season must not silently delete its
--    tournaments (unlike matches, which cascade).
ALTER TABLE public.tournaments
  ADD COLUMN IF NOT EXISTS season_id integer
  REFERENCES public.seasons(id) ON DELETE RESTRICT;

-- 3. Backfill every existing tournament to 2025-2026 (the season they were
--    created under).
UPDATE public.tournaments
SET season_id = (SELECT id FROM public.seasons WHERE name = '2025-2026')
WHERE season_id IS NULL;

-- 4. Now that all rows have a season, require it going forward.
ALTER TABLE public.tournaments
  ALTER COLUMN season_id SET NOT NULL;

-- 5. Index for season-filtered listing (mirrors idx_matches_season).
CREATE INDEX IF NOT EXISTS idx_tournaments_season
  ON public.tournaments USING btree (season_id);
