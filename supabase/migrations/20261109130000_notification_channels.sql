-- SB-1602: scoped notification channels (squad, club, global) with an audience
-- and an event filter. Replaces club_notification_channels, which allowed one
-- channel per club per platform and nothing else.
--
-- Additive: nothing reads this table until the backend change ships, and the
-- old table stays in place until that has been verified in production.

CREATE TABLE IF NOT EXISTS public.notification_channels (
    id serial PRIMARY KEY,
    scope_type text NOT NULL CHECK (scope_type IN ('club', 'team', 'global')),
    club_id integer REFERENCES public.clubs(id) ON DELETE CASCADE,
    team_id integer REFERENCES public.teams(id) ON DELETE CASCADE,
    age_group_id integer REFERENCES public.age_groups(id) ON DELETE CASCADE,
    audience text NOT NULL DEFAULT 'fans' CHECK (audience IN ('fans', 'players')),
    platform text NOT NULL,
    destination text NOT NULL,
    event_types text[],
    enabled boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,

    -- A team row is a club in one league; the age group is what makes it a
    -- squad, so a team channel without one would receive every age group.
    CONSTRAINT notification_channels_scope_shape CHECK (
        (scope_type = 'club' AND club_id IS NOT NULL AND team_id IS NULL AND age_group_id IS NULL)
        OR (scope_type = 'team' AND team_id IS NOT NULL AND age_group_id IS NOT NULL AND club_id IS NULL)
        OR (scope_type = 'global' AND club_id IS NULL AND team_id IS NULL AND age_group_id IS NULL)
    ),
    CONSTRAINT notification_channels_global_is_fans CHECK (
        scope_type <> 'global' OR audience = 'fans'
    )
);

COMMENT ON TABLE public.notification_channels IS 'Where match updates are posted: a squad, a club, or every match.';
COMMENT ON COLUMN public.notification_channels.destination IS 'Sensitive: chat id or webhook URL. Never logged or returned in full.';
COMMENT ON COLUMN public.notification_channels.event_types IS 'NULL = every event; empty array = none. Never collapse the two.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_channels_target
    ON public.notification_channels (
        scope_type,
        COALESCE(club_id, 0),
        COALESCE(team_id, 0),
        COALESCE(age_group_id, 0),
        audience,
        platform,
        destination
    );
CREATE INDEX IF NOT EXISTS idx_notification_channels_club
    ON public.notification_channels (club_id) WHERE club_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notification_channels_team
    ON public.notification_channels (team_id, age_group_id) WHERE team_id IS NOT NULL;

DROP TRIGGER IF EXISTS handle_updated_at ON public.notification_channels;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.notification_channels
    FOR EACH ROW
    EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- Every existing channel is a club channel for fans, which is what it does today.
INSERT INTO public.notification_channels
    (scope_type, club_id, audience, platform, destination, enabled, created_at, updated_at)
SELECT 'club', club_id, 'fans', platform, destination, enabled, created_at, updated_at
FROM public.club_notification_channels
ON CONFLICT DO NOTHING;

-- No policy for anon or for fans and players: destinations are secrets.
ALTER TABLE public.notification_channels ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS notification_channels_admin_all ON public.notification_channels;
CREATE POLICY notification_channels_admin_all
    ON public.notification_channels
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS notification_channels_club_manager ON public.notification_channels;
CREATE POLICY notification_channels_club_manager
    ON public.notification_channels
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles p
            LEFT JOIN public.teams t ON t.id = notification_channels.team_id
            WHERE p.id = auth.uid()
              AND p.role::text = 'club_manager'
              AND p.club_id IS NOT NULL
              AND p.club_id IN (notification_channels.club_id, t.club_id)
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles p
            LEFT JOIN public.teams t ON t.id = notification_channels.team_id
            WHERE p.id = auth.uid()
              AND p.role::text = 'club_manager'
              AND p.club_id IS NOT NULL
              AND p.club_id IN (notification_channels.club_id, t.club_id)
        )
    );

DROP POLICY IF EXISTS notification_channels_team_manager ON public.notification_channels;
CREATE POLICY notification_channels_team_manager
    ON public.notification_channels
    USING (
        scope_type = 'team' AND EXISTS (
            SELECT 1 FROM public.user_profiles p
            WHERE p.id = auth.uid()
              AND p.role::text = 'team-manager'
              AND p.team_id = notification_channels.team_id
        )
    )
    WITH CHECK (
        scope_type = 'team' AND EXISTS (
            SELECT 1 FROM public.user_profiles p
            WHERE p.id = auth.uid()
              AND p.role::text = 'team-manager'
              AND p.team_id = notification_channels.team_id
        )
    );

GRANT SELECT, INSERT, UPDATE, DELETE ON public.notification_channels TO authenticated;
GRANT ALL ON public.notification_channels TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.notification_channels_id_seq TO authenticated, service_role;
