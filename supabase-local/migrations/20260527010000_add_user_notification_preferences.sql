-- Per-event push notification preferences (SB-57).
--
-- Today the push pipeline is all-or-nothing per followed team. Fans following
-- multiple teams (especially after SB-56 widened the follow surface) get every
-- kickoff/goal/halftime/fulltime for every team. Cards are globally muted via
-- a hard-coded skip in the dispatcher.
--
-- This table lets users opt in/out per event type. Missing rows fall back to
-- code-level defaults (see backend/notifications/preferences.py), so existing
-- users get current behavior with zero backfill — only users who explicitly
-- toggle anything ever have rows here.
--
-- Composite primary key (user_id, event_type) keeps the schema extensible:
-- new event types (e.g. score_update from SB-58) just need new rows, not a
-- migration.

CREATE TABLE public.user_notification_preferences (
    user_id    uuid    NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    event_type text    NOT NULL,
    enabled    boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_type),
    CONSTRAINT user_notification_preferences_event_type_check
        CHECK (event_type IN ('kickoff', 'goal', 'halftime', 'fulltime', 'yellow_card', 'red_card'))
);

CREATE INDEX idx_user_notification_preferences_user
    ON public.user_notification_preferences(user_id);

ALTER TABLE public.user_notification_preferences ENABLE ROW LEVEL SECURITY;

-- Users see and manage only their own preferences.
CREATE POLICY user_notification_preferences_user_select
    ON public.user_notification_preferences FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY user_notification_preferences_user_insert
    ON public.user_notification_preferences FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY user_notification_preferences_user_update
    ON public.user_notification_preferences FOR UPDATE
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY user_notification_preferences_user_delete
    ON public.user_notification_preferences FOR DELETE
    USING (user_id = auth.uid());

-- Admins read all for support debugging.
CREATE POLICY user_notification_preferences_admin_all
    ON public.user_notification_preferences FOR ALL
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

COMMENT ON TABLE public.user_notification_preferences IS
    'Per-user per-event-type push notification opt-in flags. Missing rows mean "use default".';
