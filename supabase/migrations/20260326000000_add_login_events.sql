-- Migration: Add login_events table for admin user login tracking
-- Created: 2026-03-26

CREATE TABLE public.login_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid,                           -- NULL for failed logins where user not found
    username varchar(100) NOT NULL,
    client_ip varchar(45),                  -- IPv4 or IPv6
    success boolean NOT NULL,
    failure_reason varchar(100),            -- e.g. 'invalid_credentials', 'account_error'
    role varchar(50),                       -- user's role at time of login (NULL if failed)
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX login_events_user_id_idx ON public.login_events(user_id);
CREATE INDEX login_events_created_at_idx ON public.login_events(created_at DESC);
CREATE INDEX login_events_username_idx ON public.login_events(username);
CREATE INDEX login_events_success_idx ON public.login_events(success);

-- RLS: only service role and admin users can read login events
ALTER TABLE public.login_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on login_events"
    ON public.login_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
