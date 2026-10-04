-- Native iOS push: APNs device tokens + platform on the send log (SB-1236).
--
-- apns_devices   — one row per iOS install. device_token is the hex token the
--                  app gets from registerForRemoteNotifications(); it uniquely
--                  identifies (device, app, environment) to APNs, so it is the
--                  upsert key. A token re-registered by a different user moves
--                  to that user (shared family iPad).
--                  environment picks the APNs host: 'sandbox' for Xcode/debug
--                  builds, 'production' for TestFlight/App Store.
-- push_send_log  — gains apns_device_id (push_send_log.subscription_id is an FK
--                  to push_subscriptions, so an APNs device id cannot go there)
--                  and platform. platform is explicit rather than inferred from
--                  which id is set: an expired device is deleted straight after
--                  its send is logged, ON DELETE SET NULL clears apns_device_id,
--                  and the row would otherwise lose which platform it was.
--
-- RLS mirrors push_subscriptions: users manage their own devices; admins all.

-- ----------------------------------------------------------------------------
-- apns_devices
-- ----------------------------------------------------------------------------

CREATE TABLE public.apns_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    device_token text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('sandbox', 'production')),
    bundle_id text NOT NULL DEFAULT 'io.silverbeer.mt',
    device_label text,
    app_version text,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT apns_devices_device_token_unique UNIQUE (device_token)
);

CREATE INDEX idx_apns_devices_user ON public.apns_devices(user_id);

ALTER TABLE public.apns_devices ENABLE ROW LEVEL SECURITY;

-- Users see/manage only their own devices.
CREATE POLICY apns_devices_user_select
    ON public.apns_devices FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY apns_devices_user_insert
    ON public.apns_devices FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY apns_devices_user_update
    ON public.apns_devices FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY apns_devices_user_delete
    ON public.apns_devices FOR DELETE
    USING (user_id = auth.uid());

-- Admins see/manage all (support debugging, "list all devices for user X").
CREATE POLICY apns_devices_admin_all
    ON public.apns_devices FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles up
            WHERE up.id = auth.uid() AND up.role = 'admin'
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles up
            WHERE up.id = auth.uid() AND up.role = 'admin'
        )
    );

-- ----------------------------------------------------------------------------
-- push_send_log: APNs sends
-- ----------------------------------------------------------------------------

ALTER TABLE public.push_send_log
    ADD COLUMN apns_device_id uuid REFERENCES public.apns_devices(id) ON DELETE SET NULL,
    ADD COLUMN platform text NOT NULL DEFAULT 'web' CHECK (platform IN ('web', 'apns'));

COMMENT ON TABLE public.apns_devices IS
    'APNs device tokens for the native iOS app, one row per install. device_token is unique.';
COMMENT ON COLUMN public.push_send_log.platform IS
    'web = Web Push (subscription_id), apns = native iOS (apns_device_id).';
