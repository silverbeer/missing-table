-- SB-1607: who may see a notification channel's invite link.
--
-- One row per user per channel, recording how access was granted and by whom.
-- Replaces the per-platform status columns on channel_access_requests, which
-- stays in place until nothing reads it.
--
-- Additive: nothing reads these until the backend change ships.

-- The link people use to join. Unlike `destination`, which is write-only, an
-- invite link is shown, but only to a viewer with an active grant.
ALTER TABLE public.notification_channels
    ADD COLUMN IF NOT EXISTS invite_url text;

COMMENT ON COLUMN public.notification_channels.invite_url IS
    'Join link. Returned only to a viewer with an active channel_members grant who is still eligible.';

CREATE TABLE IF NOT EXISTS public.channel_members (
    id bigserial PRIMARY KEY,
    channel_id integer NOT NULL REFERENCES public.notification_channels(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    -- requested: waiting on a manager. active: may see the invite link.
    -- denied: a manager said no. revoked: access was withdrawn.
    status text NOT NULL CHECK (status IN ('requested', 'active', 'denied', 'revoked')),
    -- request: the user asked and a manager decided. invite: a manager granted it.
    -- eligible: the user joined a channel their club or squad entitles them to.
    source text NOT NULL CHECK (source IN ('request', 'invite', 'eligible')),
    decided_by uuid REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    decided_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_channel_members_channel_user UNIQUE (channel_id, user_id)
);

COMMENT ON TABLE public.channel_members IS
    'Access grants to notification channels. A grant is necessary but not sufficient: eligibility is re-checked on every read.';

CREATE INDEX IF NOT EXISTS idx_channel_members_user ON public.channel_members (user_id);
CREATE INDEX IF NOT EXISTS idx_channel_members_requested
    ON public.channel_members (channel_id) WHERE status = 'requested';

DROP TRIGGER IF EXISTS handle_updated_at ON public.channel_members;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.channel_members
    FOR EACH ROW
    EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- The backend reads and writes with the service role and applies the rules.
-- Through the API a user may read their own rows; admins may read all.
ALTER TABLE public.channel_members ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS channel_members_self_read ON public.channel_members;
CREATE POLICY channel_members_self_read
    ON public.channel_members
    FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS channel_members_admin_read ON public.channel_members;
CREATE POLICY channel_members_admin_read
    ON public.channel_members
    FOR SELECT
    USING (public.is_admin());

GRANT SELECT ON public.channel_members TO authenticated;
GRANT ALL ON public.channel_members TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.channel_members_id_seq TO service_role;
