-- Support Inbox reply delivery status (SB-1821)
--
-- The same four columns SB-1814 added to invitations, on email_messages.
-- send_admin_reply stores Resend's email id on the outbound row with
-- email_status 'sent'; the existing webhook (POST /api/webhooks/email/inbound)
-- falls through to email_messages when no invitation carries the id, and
-- records delivered / delayed / bounced / complained / failed / suppressed
-- with the same precedence and compare-and-set write.
--
-- Only outbound rows are ever tracked. email_status NULL means no tracked
-- email: an inbound message, a reply whose id could not be recorded, or one
-- sent before this migration. The admin UI renders NULL as nothing, never as
-- "not delivered".
--
-- No new table, so no backup-registry change: email_messages is already
-- backed up.
--
-- Deploy order: run `migrate prod` BEFORE the SB-1821 backend deploys. The
-- reply send is safe either way (the id is written by a separate best-effort
-- update after the insert, so a missing column never fails a reply). The
-- webhook is not: an event for any email that is not an invitation (password
-- resets, replies) now looks email_messages up by resend_email_id, and against
-- a database without the column that lookup is a 500 that Resend retries.

ALTER TABLE public.email_messages
    ADD COLUMN IF NOT EXISTS resend_email_id text,
    ADD COLUMN IF NOT EXISTS email_status text,
    ADD COLUMN IF NOT EXISTS email_status_at timestamptz,
    ADD COLUMN IF NOT EXISTS email_status_detail text;

ALTER TABLE public.email_messages
    DROP CONSTRAINT IF EXISTS email_messages_email_status_check;

ALTER TABLE public.email_messages
    ADD CONSTRAINT email_messages_email_status_check CHECK (
        email_status IS NULL
        OR email_status IN (
            'sent', 'delivered', 'delayed', 'bounced', 'complained', 'failed', 'suppressed'
        )
    );

CREATE INDEX IF NOT EXISTS idx_email_messages_resend_email_id
    ON public.email_messages (resend_email_id)
    WHERE resend_email_id IS NOT NULL;

COMMENT ON COLUMN public.email_messages.resend_email_id IS
    'Resend email id of an outbound reply. NULL for inbound messages.';
COMMENT ON COLUMN public.email_messages.email_status IS
    'Delivery of an outbound reply: sent|delivered|delayed|bounced|complained|failed|suppressed. NULL = not tracked.';
COMMENT ON COLUMN public.email_messages.email_status_at IS
    'When Resend reported email_status (the event created_at).';
COMMENT ON COLUMN public.email_messages.email_status_detail IS
    'Short generic reason for a bounce, e.g. "Permanent: Suppressed". Never the raw SMTP diagnostic.';
