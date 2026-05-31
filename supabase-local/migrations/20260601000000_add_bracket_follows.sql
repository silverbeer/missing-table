-- Bracket follows: tournament-bracket notification subscriptions.
--
-- A user follows a specific (tournament, bracket, age_group) and receives a
-- Web Push when any match in that bracket reaches a final score (fulltime).
-- A "bracket" is the tournament_group value on a match (e.g. "Bracket A");
-- one bracket can span multiple age groups, so the age_group is part of the
-- key — the user follows one age group within a bracket.
--
-- Mirrors user_team_follows (20260527000000_add_push_subscriptions.sql):
--   - FK to user_profiles(id) ON DELETE CASCADE
--   - RLS: users manage their own follows; admins read/manage all
-- The fan-out (dispatcher) reads this via the service role, bypassing RLS.

CREATE TABLE public.user_bracket_follows (
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    tournament_id integer NOT NULL REFERENCES public.tournaments(id) ON DELETE CASCADE,
    tournament_group text NOT NULL,
    age_group_id integer NOT NULL REFERENCES public.age_groups(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, tournament_id, tournament_group, age_group_id)
);

-- Fan-out hot path: "who follows this bracket?" keyed on the match's
-- (tournament_id, tournament_group, age_group_id).
CREATE INDEX idx_user_bracket_follows_bracket
    ON public.user_bracket_follows(tournament_id, tournament_group, age_group_id);

ALTER TABLE public.user_bracket_follows ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_bracket_follows_user_select
    ON public.user_bracket_follows FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY user_bracket_follows_user_insert
    ON public.user_bracket_follows FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY user_bracket_follows_user_delete
    ON public.user_bracket_follows FOR DELETE
    USING (user_id = auth.uid());

CREATE POLICY user_bracket_follows_admin_all
    ON public.user_bracket_follows FOR ALL
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

COMMENT ON TABLE public.user_bracket_follows IS
    'Which tournament brackets (tournament + group + age_group) a user follows for fulltime push notifications.';
