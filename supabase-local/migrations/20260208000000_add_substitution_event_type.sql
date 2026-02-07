-- Add 'substitution' event type to match_events and player_out_id column
-- for tracking substitution events in post-match stats

-- 1. Drop and re-add event_type check constraint to include 'substitution'
ALTER TABLE public.match_events
  DROP CONSTRAINT IF EXISTS match_events_event_type_check;

ALTER TABLE public.match_events
  ADD CONSTRAINT match_events_event_type_check
  CHECK (event_type::text = ANY (ARRAY['goal', 'message', 'status_change', 'substitution']::text[]));

-- 2. Add player_out_id column for substitution events (player being replaced)
ALTER TABLE public.match_events
  ADD COLUMN IF NOT EXISTS player_out_id integer;

-- 3. Add foreign key constraint to players table
ALTER TABLE public.match_events
  ADD CONSTRAINT match_events_player_out_id_fkey
  FOREIGN KEY (player_out_id) REFERENCES public.players(id);

-- 4. Add partial index on player_out_id for substitution lookups
CREATE INDEX IF NOT EXISTS idx_match_events_player_out_id
  ON public.match_events (player_out_id)
  WHERE player_out_id IS NOT NULL;
