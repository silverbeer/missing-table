-- SB-1604: retry failed chat posts from a worker instead of losing them.
--
-- A delivery row now keeps what is needed to send it again:
--   content          the rendered message (match text only; never a destination)
--   match_id         which match it is about, for admins reading the ledger
--   event_type       kickoff, goal, fulltime, lineup...
--   next_attempt_at  when the worker may try it next; NULL while the live path
--                    is sending it for the first time
--
-- `status` keeps its three values: 'pending' means "not finished yet" (being
-- sent, or waiting for a retry), 'sent' and 'failed' are terminal.
--
-- claim_due_notification_deliveries hands out due rows atomically (FOR UPDATE
-- SKIP LOCKED), so two backend pods during a rolling deploy never send the same
-- row twice. Each claim pushes next_attempt_at out by a lease and counts the
-- attempt, so a worker that dies mid-send leaves the row to be retried, not lost.
-- A first send that never finished (the pod restarted) is picked up once it is
-- p_stale_seconds old. Rows from before this migration carry no content and are
-- never claimed.
--
-- Expand-only: existing code ignores the new columns and never calls the function.

ALTER TABLE public.notification_deliveries ADD COLUMN IF NOT EXISTS content text;
ALTER TABLE public.notification_deliveries ADD COLUMN IF NOT EXISTS match_id integer;
ALTER TABLE public.notification_deliveries ADD COLUMN IF NOT EXISTS event_type text;
ALTER TABLE public.notification_deliveries ADD COLUMN IF NOT EXISTS next_attempt_at timestamp with time zone;

COMMENT ON COLUMN public.notification_deliveries.content IS 'The rendered message, kept so a retry posts the same text. Match text only; never a destination.';
COMMENT ON COLUMN public.notification_deliveries.next_attempt_at IS 'When the retry worker may try this row next. NULL while the first send is in flight.';

CREATE INDEX IF NOT EXISTS idx_notification_deliveries_due
    ON public.notification_deliveries (next_attempt_at)
    WHERE status = 'pending';

CREATE OR REPLACE FUNCTION public.claim_due_notification_deliveries(
    p_limit integer,
    p_lease_seconds integer,
    p_stale_seconds integer
)
RETURNS SETOF public.notification_deliveries
LANGUAGE sql
SET search_path = public
AS $$
    WITH due AS (
        SELECT id
        FROM public.notification_deliveries
        WHERE status = 'pending'
          AND content IS NOT NULL
          AND COALESCE(next_attempt_at, created_at + make_interval(secs => p_stale_seconds)) <= now()
        ORDER BY COALESCE(next_attempt_at, created_at)
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.notification_deliveries d
    SET next_attempt_at = now() + make_interval(secs => p_lease_seconds),
        attempts = d.attempts + 1
    FROM due
    WHERE d.id = due.id
    RETURNING d.*;
$$;

COMMENT ON FUNCTION public.claim_due_notification_deliveries(integer, integer, integer) IS
    'SB-1604: atomically claim due chat posts for the retry worker. Service role only.';

REVOKE ALL ON FUNCTION public.claim_due_notification_deliveries(integer, integer, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_due_notification_deliveries(integer, integer, integer) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_notification_deliveries(integer, integer, integer) TO service_role;
