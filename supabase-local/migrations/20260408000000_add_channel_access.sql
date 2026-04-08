-- Migration: add Telegram/Discord channel access requests
-- Adds handle columns to user_profiles and a dedicated channel_access_requests table
-- for the workflow where users request to join their team's Telegram/Discord channels.

-- ============================================================
-- 1. Status enum
-- ============================================================
CREATE TYPE public.channel_request_status AS ENUM ('none', 'pending', 'approved', 'denied');

-- ============================================================
-- 2. Handle columns on user_profiles
-- ============================================================
ALTER TABLE public.user_profiles
    ADD COLUMN telegram_handle varchar(64),
    ADD COLUMN discord_handle  varchar(64);

-- ============================================================
-- 3. channel_access_requests table
-- ============================================================
CREATE TABLE public.channel_access_requests (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    team_id                 integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    telegram_handle         varchar(64),
    discord_handle          varchar(64),
    telegram_status         public.channel_request_status NOT NULL DEFAULT 'none',
    discord_status          public.channel_request_status NOT NULL DEFAULT 'none',
    telegram_reviewed_by    uuid REFERENCES auth.users(id),
    telegram_reviewed_at    timestamptz,
    discord_reviewed_by     uuid REFERENCES auth.users(id),
    discord_reviewed_at     timestamptz,
    admin_notes             text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT channel_access_unique_user_team UNIQUE (user_id, team_id)
);

-- ============================================================
-- 4. Indexes
-- ============================================================
CREATE INDEX idx_channel_access_team_id
    ON public.channel_access_requests(team_id);

CREATE INDEX idx_channel_access_user_id
    ON public.channel_access_requests(user_id);

CREATE INDEX idx_channel_access_pending
    ON public.channel_access_requests(team_id)
    WHERE telegram_status = 'pending' OR discord_status = 'pending';

-- ============================================================
-- 5. updated_at trigger (mirrors invite_requests pattern)
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_channel_access_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_channel_access_updated_at
    BEFORE UPDATE ON public.channel_access_requests
    FOR EACH ROW
    EXECUTE FUNCTION public.update_channel_access_updated_at();

-- ============================================================
-- 6. Row Level Security
-- ============================================================
ALTER TABLE public.channel_access_requests ENABLE ROW LEVEL SECURITY;

-- Users can read their own rows
CREATE POLICY channel_access_self_select
    ON public.channel_access_requests
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own rows
CREATE POLICY channel_access_self_insert
    ON public.channel_access_requests
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own rows only while no platform is approved
-- (prevents users from modifying after admin has approved them)
CREATE POLICY channel_access_self_update
    ON public.channel_access_requests
    FOR UPDATE
    USING (
        auth.uid() = user_id
        AND telegram_status <> 'approved'
        AND discord_status <> 'approved'
    )
    WITH CHECK (auth.uid() = user_id);

-- Admins can view all rows (admin ops also go through service_client which bypasses RLS)
CREATE POLICY channel_access_admin_select
    ON public.channel_access_requests
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );
