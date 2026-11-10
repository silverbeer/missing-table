-- SB-1605: a name managers give a channel, and a fast "last delivery" lookup.
--
-- A destination is write-only, and a Slack webhook URL does not carry the
-- channel's name, so "ends in H27c" was all a manager could see. `label` is
-- the manager's own name for it (e.g. "#ifa-u15-live"). It is not secret.
--
-- Additive: nothing reads these until the backend change ships.

ALTER TABLE public.notification_channels
    ADD COLUMN IF NOT EXISTS label text;

ALTER TABLE public.notification_channels
    DROP CONSTRAINT IF EXISTS notification_channels_label_length;
ALTER TABLE public.notification_channels
    ADD CONSTRAINT notification_channels_label_length
    CHECK (label IS NULL OR char_length(label) BETWEEN 1 AND 80);

COMMENT ON COLUMN public.notification_channels.label IS
    'Manager-chosen name for the channel. Not secret; NULL when none was given.';

-- The setup screen shows each channel's most recent delivery.
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_channel_recent
    ON public.notification_deliveries (channel_id, created_at DESC);
