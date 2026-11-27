-- Invitation email delivery status (SB-1814)
--
-- "pending" on an invitation means "not redeemed yet", and says nothing about
-- whether the email ever arrived. Resend knows: the send returns an email id,
-- and the existing webhook (POST /api/webhooks/email/inbound) now also takes
-- the email.sent / delivered / delivery_delayed / bounced / complained /
-- failed / suppressed events and records the outcome here.
--
-- email_status NULL means no tracked email: the invite has no address, the
-- send failed before Resend accepted it, or it predates this migration. The
-- admin UI renders NULL as nothing, never as "not delivered".
--
-- email_status_detail is a short, generic reason ("Permanent: Suppressed"),
-- never the raw SMTP diagnostic.
--
-- No new table, so no backup-registry change: invitations is already backed up.
--
-- Deploy order: run `migrate prod` BEFORE enabling the extra events on the
-- Resend webhook. The webhook looks invitations up by resend_email_id, so a
-- delivery event against a database without the column is a 500 that Resend
-- retries. The send path tolerates the columns being absent (recording the id
-- is best effort and never fails an invite).

ALTER TABLE public.invitations
    ADD COLUMN IF NOT EXISTS resend_email_id text,
    ADD COLUMN IF NOT EXISTS email_status text,
    ADD COLUMN IF NOT EXISTS email_status_at timestamptz,
    ADD COLUMN IF NOT EXISTS email_status_detail text;

ALTER TABLE public.invitations
    DROP CONSTRAINT IF EXISTS invitations_email_status_check;

ALTER TABLE public.invitations
    ADD CONSTRAINT invitations_email_status_check CHECK (
        email_status IS NULL
        OR email_status IN (
            'sent', 'delivered', 'delayed', 'bounced', 'complained', 'failed', 'suppressed'
        )
    );

CREATE INDEX IF NOT EXISTS idx_invitations_resend_email_id
    ON public.invitations (resend_email_id)
    WHERE resend_email_id IS NOT NULL;

COMMENT ON COLUMN public.invitations.resend_email_id IS
    'Resend email id of the latest invitation email; a resend replaces it.';
COMMENT ON COLUMN public.invitations.email_status IS
    'Delivery of the latest invitation email: sent|delivered|delayed|bounced|complained|failed|suppressed. NULL = not tracked.';
COMMENT ON COLUMN public.invitations.email_status_at IS
    'When Resend reported email_status (the event created_at).';
COMMENT ON COLUMN public.invitations.email_status_detail IS
    'Short generic reason for a bounce or failure, e.g. "Permanent: Suppressed". Never the raw SMTP diagnostic.';
