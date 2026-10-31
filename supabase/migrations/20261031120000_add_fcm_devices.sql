-- Native Android push: FCM device registrations + platform on the send log (SB-1463).
--
-- fcm_devices    — one row per Android install. fid is the Firebase
--                  Installation ID the app gets from
--                  FirebaseInstallations.getId(); FCM HTTP v1 addresses a
--                  device by it (Message.fid; Message.token is deprecated).
--                  It is the upsert key: an fid re-registered by a different
--                  user moves to that user (shared family tablet).
-- push_send_log  — gains fcm_device_id (same reasoning as apns_device_id: the
--                  subscription_id FK points at push_subscriptions), and the
--                  platform CHECK widens to include 'fcm'.
--
-- Follows SB-1247 (20261005000000_lock_match_events_lineups_writes): RLS on,
-- no policies, no client grants. The backend reads and writes it with the
-- service key; device ids are never exposed to PostgREST directly. Supabase
-- no longer auto-grants new tables, so service_role is granted explicitly.

-- ----------------------------------------------------------------------------
-- fcm_devices
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.fcm_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    fid text NOT NULL,
    device_label text,
    app_version text,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fcm_devices_fid_unique UNIQUE (fid)
);

CREATE INDEX IF NOT EXISTS idx_fcm_devices_user ON public.fcm_devices(user_id);

ALTER TABLE public.fcm_devices ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fcm_devices FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.fcm_devices TO service_role;

-- ----------------------------------------------------------------------------
-- push_send_log: FCM sends
-- ----------------------------------------------------------------------------

ALTER TABLE public.push_send_log
    ADD COLUMN IF NOT EXISTS fcm_device_id uuid REFERENCES public.fcm_devices(id) ON DELETE SET NULL;

-- Keeps the ON DELETE SET NULL from fcm_devices off a full scan of the log.
CREATE INDEX IF NOT EXISTS idx_push_send_log_fcm_device
    ON public.push_send_log(fcm_device_id) WHERE fcm_device_id IS NOT NULL;

-- The apns migration declared the CHECK inline, so Postgres named it
-- push_send_log_platform_check.
ALTER TABLE public.push_send_log DROP CONSTRAINT IF EXISTS push_send_log_platform_check;
ALTER TABLE public.push_send_log
    ADD CONSTRAINT push_send_log_platform_check CHECK (platform IN ('web', 'apns', 'fcm'));

COMMENT ON TABLE public.fcm_devices IS
    'Firebase Installation IDs for the native Android app, one row per install (SB-1463). fid is unique. Backend-only.';
COMMENT ON COLUMN public.push_send_log.platform IS
    'web = Web Push (subscription_id), apns = native iOS (apns_device_id), fcm = native Android (fcm_device_id).';
