-- Audit log for admin edits to user accounts (SB-803)
--
-- Editing a user's role is privilege modification, and until now there was
-- nowhere to record it. `audit_events` is the match/score audit — it is keyed
-- by team, age group, league, division and season — so it cannot hold "who
-- changed whose role". `login_events` records authentication, not changes.
--
-- One row per admin edit, storing the actor, the target, and the before/after
-- of every field touched.

CREATE TABLE IF NOT EXISTS public.admin_user_audit_log (
    id            bigserial PRIMARY KEY,
    -- Who made the change. No FK: the log must survive the actor's account
    -- being deleted, which is exactly when it matters most.
    actor_id      uuid NOT NULL,
    actor_username text,
    -- Whose account changed. Same reasoning — no FK.
    target_id     uuid NOT NULL,
    target_username text,
    -- Only the fields that actually changed, as {field: {from, to}}. Storing
    -- the whole profile would bury the change and duplicate PII.
    changes       jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- The two questions this table gets asked: "what happened to this account?"
-- and "what has this admin been doing?"
CREATE INDEX IF NOT EXISTS admin_user_audit_log_target_idx
    ON public.admin_user_audit_log (target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS admin_user_audit_log_actor_idx
    ON public.admin_user_audit_log (actor_id, created_at DESC);

COMMENT ON TABLE public.admin_user_audit_log IS
    'Admin edits to user_profiles (role/team/club). Written by PATCH /api/admin/users/{id}.';

-- RLS on, with no policy: the backend reaches this table with the service key,
-- which bypasses RLS. No client should read an audit log directly.
ALTER TABLE public.admin_user_audit_log ENABLE ROW LEVEL SECURITY;
