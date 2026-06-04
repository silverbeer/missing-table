-- Update matches_match_status_check to include 'forfeit'
-- The original constraint only allowed: scheduled, tbd, live, completed, postponed, cancelled
ALTER TABLE public.matches
  DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE public.matches
  ADD CONSTRAINT matches_match_status_check
    CHECK (match_status IN ('scheduled', 'tbd', 'live', 'completed', 'postponed', 'cancelled', 'forfeit'));
