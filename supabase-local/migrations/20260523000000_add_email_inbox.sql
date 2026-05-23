-- Migration: Support Inbox (SB-35 Phase 1)
-- Description: Tables for inbound + outbound email threads tied to support@missingtable.com.
--              Inbound webhook (Resend Inbound) writes to these; admin UI (Phase 2/3) reads.
-- Date: 2026-05-23
-- Related: SB-35

-- Ensure moddatetime extension is available for the updated_at trigger.
CREATE EXTENSION IF NOT EXISTS moddatetime SCHEMA extensions;

-- ----------------------------------------------------------------------------
-- 1) Case-number sequence — every thread gets a monotonically-increasing
--    integer rendered as "MT-{n}" in the UI and subject lines.
-- ----------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.email_thread_case_seq START 1;

-- ----------------------------------------------------------------------------
-- 2) email_threads — one row per conversation with an external participant.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.email_threads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number integer NOT NULL UNIQUE DEFAULT nextval('public.email_thread_case_seq'),
    subject text NOT NULL,
    participant_email text NOT NULL,
    participant_name text,
    status text NOT NULL DEFAULT 'new',
    last_message_at timestamptz NOT NULL DEFAULT now(),
    unread_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_threads_status_check
        CHECK (status IN ('new', 'awaiting_admin', 'awaiting_user', 'resolved', 'spam'))
);

ALTER SEQUENCE public.email_thread_case_seq OWNED BY public.email_threads.case_number;

COMMENT ON TABLE public.email_threads IS 'Support-inbox threads keyed by case_number (MT-{n}). Auto-transitions via status enum.';
COMMENT ON COLUMN public.email_threads.case_number IS 'Sequential MT case number, rendered as "MT-{case_number}" and embedded in outbound subjects as a threading fallback.';
COMMENT ON COLUMN public.email_threads.status IS 'Lifecycle: new (first inbound) → awaiting_admin (user replied) → awaiting_user (admin replied) → resolved | spam (manual).';

CREATE INDEX IF NOT EXISTS idx_email_threads_status_last_message
    ON public.email_threads (status, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_threads_case_number
    ON public.email_threads (case_number);
CREATE INDEX IF NOT EXISTS idx_email_threads_participant_email
    ON public.email_threads (participant_email);

DROP TRIGGER IF EXISTS handle_updated_at ON public.email_threads;
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.email_threads
    FOR EACH ROW
    EXECUTE PROCEDURE extensions.moddatetime(updated_at);

-- ----------------------------------------------------------------------------
-- 3) email_messages — one row per inbound or outbound message in a thread.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.email_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid NOT NULL REFERENCES public.email_threads(id) ON DELETE CASCADE,
    direction text NOT NULL,
    message_id text NOT NULL UNIQUE,
    in_reply_to text,
    "references" text,
    from_email text NOT NULL,
    from_name text,
    to_email text NOT NULL,
    subject text NOT NULL,
    body_text text,
    body_html text,
    had_attachments boolean NOT NULL DEFAULT false,
    raw_payload jsonb,
    sent_by_user_id uuid REFERENCES public.user_profiles(id),
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_messages_direction_check
        CHECK (direction IN ('inbound', 'outbound'))
);

COMMENT ON TABLE public.email_messages IS 'Individual inbound and outbound messages in support threads. message_id is the RFC 5322 Message-ID (angle brackets stripped) and is unique for idempotent webhook ingest.';
COMMENT ON COLUMN public.email_messages.had_attachments IS 'True when the inbound payload included attachments; the attachments themselves are dropped (not stored). UI surfaces a "reply via your email client to see attachments" notice.';
COMMENT ON COLUMN public.email_messages.body_html IS 'Sanitized HTML body (bleach allowlist). Never store unsanitized HTML from the inbound webhook.';
COMMENT ON COLUMN public.email_messages.raw_payload IS 'Full provider payload (Resend ReceivedEmail) for debugging. May be cleared after a retention window.';

CREATE INDEX IF NOT EXISTS idx_email_messages_thread_created
    ON public.email_messages (thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_email_messages_message_id
    ON public.email_messages (message_id);
CREATE INDEX IF NOT EXISTS idx_email_messages_in_reply_to
    ON public.email_messages (in_reply_to)
    WHERE in_reply_to IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 4) Row-level security — admin-only for now. Phase 2 admin API uses the
--    service role for inserts/updates and goes through these policies for
--    admin-user reads via the standard auth path.
-- ----------------------------------------------------------------------------
ALTER TABLE public.email_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS email_threads_admin_all ON public.email_threads;
CREATE POLICY email_threads_admin_all
    ON public.email_threads
    USING (public.is_admin())
    WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS email_messages_admin_all ON public.email_messages;
CREATE POLICY email_messages_admin_all
    ON public.email_messages
    USING (public.is_admin())
    WITH CHECK (public.is_admin());
