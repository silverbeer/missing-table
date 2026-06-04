-- Add 'red_card' and 'yellow_card' event types to match_events
-- so cards appear in the match timeline alongside goals and substitutions.

ALTER TABLE public.match_events
  DROP CONSTRAINT IF EXISTS match_events_event_type_check;

ALTER TABLE public.match_events
  ADD CONSTRAINT match_events_event_type_check
  CHECK (event_type::text = ANY (ARRAY['goal', 'message', 'status_change', 'substitution', 'red_card', 'yellow_card']::text[]));
