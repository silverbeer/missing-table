-- SB-1606: one thread per match per channel, Discord first.
--
-- notification_channels.post_as_threads: the manager says this channel is a
-- forum, so each match gets its own post and every update for that match goes
-- into it. Off (the default) keeps today's flat posts. A platform without
-- thread support ignores it.
--
-- notification_threads: which thread holds a match on a channel. The unique
-- (channel_id, match_id) is what stops two simultaneous goals creating two
-- threads: the sender inserts the row first and only the winner creates the
-- thread; the others wait for thread_ref. thread_name is kept so whoever
-- finishes the job (a retry, or a takeover of a stale claim) names it the same.
--
-- Expand-only: nothing reads either until the code ships.

ALTER TABLE public.notification_channels
    ADD COLUMN IF NOT EXISTS post_as_threads boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.notification_channels.post_as_threads IS
    'Post each match as its own thread (a Discord forum post) and its updates into it. Ignored by platforms without threads.';

CREATE TABLE IF NOT EXISTS public.notification_threads (
    id bigserial PRIMARY KEY,
    channel_id integer NOT NULL REFERENCES public.notification_channels(id) ON DELETE CASCADE,
    match_id integer NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    thread_name text NOT NULL,
    thread_ref text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_notification_threads_channel_match UNIQUE (channel_id, match_id)
);

COMMENT ON TABLE public.notification_threads IS 'The platform thread (Discord forum post) holding one match on one channel. SB-1606.';
COMMENT ON COLUMN public.notification_threads.thread_ref IS 'The platform thread id; NULL while the thread is being created.';

DROP TRIGGER IF EXISTS handle_updated_at ON public.notification_threads;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.notification_threads
    FOR EACH ROW
    EXECUTE PROCEDURE extensions.moddatetime(updated_at);

ALTER TABLE public.notification_threads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notification_threads_admin_read ON public.notification_threads;
CREATE POLICY notification_threads_admin_read
    ON public.notification_threads
    FOR SELECT
    USING (public.is_admin());

GRANT SELECT ON public.notification_threads TO authenticated;
GRANT ALL ON public.notification_threads TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.notification_threads_id_seq TO service_role;
