-- SB-1600: the set of platforms now lives in the adapter registry
-- (backend/notifications/registry.py), which the API validates against.
-- Keeping a copy here would mean a migration for every new platform.
ALTER TABLE public.club_notification_channels
    DROP CONSTRAINT IF EXISTS club_notification_channels_platform_check;
