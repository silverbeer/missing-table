-- Push notifications: subscriptions + team-follows + send log.
--
-- Backs SB-51 (slice 5 of the mobile app epic SB-44). Three tables:
--   push_subscriptions  — one row per (user, device) combination. Endpoint URL
--                         comes from PushManager.subscribe() on the client and
--                         identifies that browser+device to the push service.
--   user_team_follows   — many-to-many. A user can follow any number of teams
--                         across any number of clubs (cross-club by design —
--                         see project_engagement_flywheel memory).
--   push_send_log       — append-only audit of every push send attempt. Useful
--                         for "I'm not getting notifications" debugging and
--                         delivery analytics.
--
-- RLS: users manage their own subscriptions and follows; admins read all.
-- push_send_log is service-role write, admin-only read.

-- ----------------------------------------------------------------------------
-- push_subscriptions
-- ----------------------------------------------------------------------------

CREATE TABLE public.push_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    endpoint text NOT NULL,
    p256dh_key text NOT NULL,
    auth_key text NOT NULL,
    device_label text,
    user_agent text,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT push_subscriptions_endpoint_unique UNIQUE (endpoint)
);

CREATE INDEX idx_push_subscriptions_user ON public.push_subscriptions(user_id);

ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;

-- Users see/manage only their own subscriptions.
CREATE POLICY push_subscriptions_user_select
    ON public.push_subscriptions FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY push_subscriptions_user_insert
    ON public.push_subscriptions FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY push_subscriptions_user_update
    ON public.push_subscriptions FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY push_subscriptions_user_delete
    ON public.push_subscriptions FOR DELETE
    USING (user_id = auth.uid());

-- Admins see/manage all (support debugging, "list all devices for user X").
CREATE POLICY push_subscriptions_admin_all
    ON public.push_subscriptions FOR ALL
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
-- user_team_follows
-- ----------------------------------------------------------------------------

CREATE TABLE public.user_team_follows (
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    team_id integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, team_id)
);

CREATE INDEX idx_user_team_follows_team ON public.user_team_follows(team_id);

ALTER TABLE public.user_team_follows ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_team_follows_user_select
    ON public.user_team_follows FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY user_team_follows_user_insert
    ON public.user_team_follows FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY user_team_follows_user_delete
    ON public.user_team_follows FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY user_team_follows_admin_all
    ON public.user_team_follows FOR ALL
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
-- push_send_log
-- ----------------------------------------------------------------------------

CREATE TABLE public.push_send_log (
    id bigserial PRIMARY KEY,
    subscription_id uuid REFERENCES public.push_subscriptions(id) ON DELETE SET NULL,
    user_id uuid,
    match_id integer,
    event_type text NOT NULL,
    status text NOT NULL,
    http_status integer,
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_push_send_log_user_created ON public.push_send_log(user_id, created_at DESC);
CREATE INDEX idx_push_send_log_match_created ON public.push_send_log(match_id, created_at DESC);

ALTER TABLE public.push_send_log ENABLE ROW LEVEL SECURITY;

-- No user-level access. Writes are service-role (backend) only.
-- Admins can read for support.
CREATE POLICY push_send_log_admin_select
    ON public.push_send_log FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles up
            WHERE up.id = auth.uid() AND up.role = 'admin'
        )
    );

-- Grants for the backend service role bypass RLS for writes (standard pattern).

COMMENT ON TABLE public.push_subscriptions IS
    'Web Push subscriptions registered per (user, device). Endpoint is the push service URL.';
COMMENT ON TABLE public.user_team_follows IS
    'Many-to-many: which teams a user follows. Cross-club by design.';
COMMENT ON TABLE public.push_send_log IS
    'Append-only log of every push send attempt; used for delivery debugging.';
