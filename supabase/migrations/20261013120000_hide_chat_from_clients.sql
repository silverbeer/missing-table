-- SB-1329: live chat was readable with the public anon key.
--
-- match_events_select_policy was `USING (is_deleted = false)` for every role, and the
-- anon key ships in the web bundle and the iOS app. So anyone, signed in or not, could
-- read every chat message (text + username) through PostgREST, and Realtime
-- postgres_changes streamed each new message to every subscriber — including chat
-- from users the viewer had blocked (SB-1309).
--
-- After this migration clients cannot read chat rows at all. The API (service key,
-- bypasses RLS) is the only reader, and it applies blocks (and, from SB-1330, club
-- rooms). Goals, cards, subs and status changes stay readable, so the live score
-- keeps streaming over Realtime as before.
--
-- Chat now reaches clients through a doorbell: live_chat_signals holds one row per
-- match carrying no content, only when chat last changed. The backend touches it on
-- every post and delete; clients subscribe to it over Realtime and re-read chat from
-- /api/matches/{id}/live/events when it rings.

-- 1. Chat rows are no longer visible to clients.
DROP POLICY IF EXISTS match_events_select_policy ON public.match_events;
CREATE POLICY match_events_select_policy ON public.match_events
    FOR SELECT
    USING (is_deleted = false AND event_type <> 'message');

-- 2. The doorbell.
CREATE TABLE IF NOT EXISTS public.live_chat_signals (
    match_id integer PRIMARY KEY,
    changed_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.live_chat_signals IS
    'SB-1329: per-match "chat changed" signal for Realtime. No content; clients re-read chat through the API.';

ALTER TABLE public.live_chat_signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS live_chat_signals_select_policy ON public.live_chat_signals;
CREATE POLICY live_chat_signals_select_policy ON public.live_chat_signals
    FOR SELECT
    USING (true);

-- Read-only for clients; the backend writes it with the service key.
REVOKE ALL ON public.live_chat_signals FROM anon, authenticated;
GRANT SELECT ON public.live_chat_signals TO anon, authenticated;

-- Stream it. The publication exists on hosted Supabase; guard for stacks without it.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime')
       AND NOT EXISTS (
           SELECT 1 FROM pg_publication_tables
           WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'live_chat_signals'
       ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.live_chat_signals;
    END IF;
END
$$;
