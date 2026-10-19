-- SB-1351: record a player changing position mid-match during live scoring.
--
-- A position_change event says "player_id now plays <position>" (a formation
-- position code such as ST, RW, LCB). Clients rebuild the current XI from the
-- saved starting lineup plus substitution and position_change events replayed
-- oldest-first.

-- 1. Allow the new event type (keeps every existing type).
ALTER TABLE public.match_events
  DROP CONSTRAINT IF EXISTS match_events_event_type_check;

ALTER TABLE public.match_events
  ADD CONSTRAINT match_events_event_type_check
  CHECK (event_type::text = ANY (ARRAY[
    'goal', 'message', 'status_change', 'substitution', 'red_card', 'yellow_card', 'position_change'
  ]::text[]));

-- 2. The player's new position (position_change events only).
ALTER TABLE public.match_events
  ADD COLUMN IF NOT EXISTS position text;

COMMENT ON COLUMN public.match_events.position IS
  'SB-1351: formation position code the player moved to (position_change events only); NULL otherwise.';
