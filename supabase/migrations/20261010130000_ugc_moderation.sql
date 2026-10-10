-- SB-1309: moderation for live match chat (App Store guideline 1.2).
--
-- content_reports  — one row per (chat message, reporter). The reported text,
--                    author and match are copied onto the row: chat messages
--                    expire and are hard-deleted after 10 days
--                    (MatchEventDAO.cleanup_expired_messages), and a report
--                    must still say what was reported after that. event_id is
--                    therefore ON DELETE SET NULL, not CASCADE.
-- user_blocks      — who has blocked whom. The API hides a blocked author's
--                    events from the blocker.
-- user_profiles.chat_banned_at — set by an admin acting on a report; a
--                    banned user can no longer post chat messages.
--
-- Both tables follow SB-1247 (20261005000000_lock_match_events_lineups_writes):
-- RLS on, no policies, no client grants. The backend reads and writes them
-- with the service key; a user's block list and reports are never exposed to
-- PostgREST directly.

-- ----------------------------------------------------------------------------
-- content_reports
-- ----------------------------------------------------------------------------

CREATE TABLE public.content_reports (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id integer REFERENCES public.match_events(id) ON DELETE SET NULL,
    match_id integer NOT NULL,
    reporter_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    reported_user_id uuid REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    reported_username varchar(100),
    message_text text NOT NULL,
    reason text NOT NULL CHECK (reason IN ('spam', 'harassment', 'hate', 'sexual', 'other')),
    details text CHECK (details IS NULL OR char_length(details) <= 500),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'actioned', 'dismissed')),
    action text CHECK (action IS NULL OR action IN ('dismiss', 'delete_message', 'ban_user')),
    resolved_by uuid REFERENCES public.user_profiles(id) ON DELETE SET NULL,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT content_reports_event_reporter_unique UNIQUE (event_id, reporter_id)
);

CREATE INDEX idx_content_reports_status_created ON public.content_reports(status, created_at DESC);

ALTER TABLE public.content_reports ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.content_reports FROM anon, authenticated;

COMMENT ON TABLE public.content_reports IS
    'Chat message reports (SB-1309). Snapshot of the reported message; written and read by the backend only.';

-- ----------------------------------------------------------------------------
-- user_blocks
-- ----------------------------------------------------------------------------

CREATE TABLE public.user_blocks (
    blocker_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    blocked_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (blocker_id, blocked_id),
    CONSTRAINT user_blocks_not_self CHECK (blocker_id <> blocked_id)
);

ALTER TABLE public.user_blocks ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.user_blocks FROM anon, authenticated;

COMMENT ON TABLE public.user_blocks IS
    'Users a user has blocked (SB-1309). The API hides blocked authors'' match events from the blocker.';

-- ----------------------------------------------------------------------------
-- user_profiles.chat_banned_at
-- ----------------------------------------------------------------------------

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS chat_banned_at timestamptz;

COMMENT ON COLUMN public.user_profiles.chat_banned_at IS
    'When an admin removed this user from live match chat (SB-1309). Null = may post.';
