-- SB-1603: one row per (channel, match event). The unique constraint is what
-- stops a resent event from posting twice: the sender claims the row first and
-- only posts if the claim succeeds.
--
-- Additive: nothing reads this table until the backend change ships.
-- Holds no destination; channel_id is the only link to where a message went.

CREATE TABLE IF NOT EXISTS public.notification_deliveries (
    id bigserial PRIMARY KEY,
    channel_id integer NOT NULL REFERENCES public.notification_channels(id) ON DELETE CASCADE,
    event_key text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    provider_message_ref text,
    error text,
    attempts integer NOT NULL DEFAULT 1,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_notification_deliveries_channel_event UNIQUE (channel_id, event_key)
);

COMMENT ON TABLE public.notification_deliveries IS 'What was posted to each notification channel, one row per match event.';
COMMENT ON COLUMN public.notification_deliveries.event_key IS 'Stable identity of the match event; see backend/notifications/event_keys.py.';
COMMENT ON COLUMN public.notification_deliveries.provider_message_ref IS 'The platform message id; NULL when the platform returns none (a webhook answering 204).';
COMMENT ON COLUMN public.notification_deliveries.error IS 'Sanitized: never a destination, token or provider URL.';

DROP TRIGGER IF EXISTS handle_updated_at ON public.notification_deliveries;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.notification_deliveries
    FOR EACH ROW
    EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- The backend writes with the service role; admins may read for diagnostics.
ALTER TABLE public.notification_deliveries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notification_deliveries_admin_read ON public.notification_deliveries;
CREATE POLICY notification_deliveries_admin_read
    ON public.notification_deliveries
    FOR SELECT
    USING (public.is_admin());

GRANT SELECT ON public.notification_deliveries TO authenticated;
GRANT ALL ON public.notification_deliveries TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.notification_deliveries_id_seq TO service_role;
