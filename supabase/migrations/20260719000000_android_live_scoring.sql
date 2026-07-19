-- Android live-scoring support (SB: offline-first native app)
-- 1. Assists on goal events (assist_player_id + denormalized name for display)
-- 2. client_event_id: client-generated UUID for idempotent event creation.
--    The partial unique index is the server-side gate that makes offline sync
--    replays exactly-once (a replayed POST with the same client_event_id must
--    not double-increment the score).

ALTER TABLE public.match_events
  ADD COLUMN IF NOT EXISTS assist_player_id integer REFERENCES public.players(id),
  ADD COLUMN IF NOT EXISTS assist_player_name varchar(200),
  ADD COLUMN IF NOT EXISTS client_event_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS uq_match_events_client_event_id
  ON public.match_events (client_event_id)
  WHERE client_event_id IS NOT NULL;

COMMENT ON COLUMN public.match_events.assist_player_id IS 'Roster player credited with the assist (goal events only)';
COMMENT ON COLUMN public.match_events.assist_player_name IS 'Denormalized assister display name for timeline rendering';
COMMENT ON COLUMN public.match_events.client_event_id IS 'Client-generated UUID for idempotent offline sync; unique when present';
