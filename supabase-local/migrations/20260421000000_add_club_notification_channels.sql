-- Migration: Add club_notification_channels + clubs.timezone
-- Description: Per-club Telegram / Discord channels for live match notifications.
-- Date: 2026-04-21
-- Related: Phase 2 of #315 (live match notifications feature)

-- Ensure moddatetime extension is available for the updated_at trigger.
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- ----------------------------------------------------------------------------
-- 1) clubs.timezone — used when rendering match times in notifications.
--    Home club's timezone is used regardless of the destination channel.
-- ----------------------------------------------------------------------------
ALTER TABLE public.clubs
    ADD COLUMN IF NOT EXISTS timezone text NOT NULL DEFAULT 'America/New_York';

COMMENT ON COLUMN public.clubs.timezone IS 'IANA timezone name used when formatting match times in notifications (e.g. America/New_York).';

-- ----------------------------------------------------------------------------
-- 2) club_notification_channels — one row per (club, platform).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.club_notification_channels (
    id serial PRIMARY KEY,
    club_id integer NOT NULL REFERENCES public.clubs(id) ON DELETE CASCADE,
    platform text NOT NULL CHECK (platform IN ('telegram', 'discord')),
    destination text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT club_notification_channels_club_platform_unique UNIQUE (club_id, platform)
);

COMMENT ON TABLE public.club_notification_channels IS 'Per-club Telegram chat_ids and Discord webhook URLs for live match notifications.';
COMMENT ON COLUMN public.club_notification_channels.destination IS 'Sensitive: Telegram chat_id or Discord webhook URL. Never logged. Never returned to the frontend in full.';

CREATE INDEX IF NOT EXISTS idx_club_notification_channels_club_enabled
    ON public.club_notification_channels (club_id, enabled);

-- ----------------------------------------------------------------------------
-- 3) updated_at trigger (mirrors backend/sql/021_add_updated_at_trigger.sql).
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS handle_updated_at ON public.club_notification_channels;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.club_notification_channels
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime(updated_at);

-- ----------------------------------------------------------------------------
-- 4) Row-level security.
--    - admin: full access on any row
--    - club_manager: full access on rows where club_id = their own club
--    - everyone else: no access
-- ----------------------------------------------------------------------------
ALTER TABLE public.club_notification_channels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS club_notification_channels_admin_all ON public.club_notification_channels;
CREATE POLICY club_notification_channels_admin_all
    ON public.club_notification_channels
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS club_notification_channels_club_manager_own_club ON public.club_notification_channels;
CREATE POLICY club_notification_channels_club_manager_own_club
    ON public.club_notification_channels
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE user_profiles.id = auth.uid()
              AND user_profiles.role::text = 'club_manager'
              AND user_profiles.club_id = club_notification_channels.club_id
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE user_profiles.id = auth.uid()
              AND user_profiles.role::text = 'club_manager'
              AND user_profiles.club_id = club_notification_channels.club_id
        )
    );
