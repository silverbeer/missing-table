-- Match ingest failures, recorded rather than logged (SB-829)
--
-- Before this table, a match the worker could not resolve produced a
-- logger.error in a pod and nothing else. The scraper's Telegram report could
-- not see it either: that report counts errors from the RabbitMQ *publish*,
-- which succeeds regardless of whether missing-table went on to accept the
-- match. A load where every team name was unknown reported
-- "1432 found, 1432 submitted, 0 errors" and landed nothing.
--
-- One row per distinct unresolved name, not per dropped match: a season load
-- that dies on seven spellings should read as seven problems with counts, not
-- as four hundred alerts.
--
-- Each row is also directly actionable — the fix for an unresolved team name
-- is one `mt team alias add` (SB-822/SB-824) — which is why raw_name is kept
-- verbatim rather than normalised.

CREATE TABLE IF NOT EXISTS public.ingest_failures (
    id          serial PRIMARY KEY,
    kind        text NOT NULL,
    raw_name    text NOT NULL,
    -- The league as the FEED named it, which is not necessarily a league we
    -- have. An unmapped competition name is itself a finding.
    league      text,
    source      text NOT NULL DEFAULT 'match-scraper',
    -- One example of what was dropped, for the alert line. Not an audit trail;
    -- the count is the magnitude and this is the illustration.
    sample      text,
    match_count integer NOT NULL DEFAULT 1,
    first_seen  timestamptz NOT NULL DEFAULT now(),
    last_seen   timestamptz NOT NULL DEFAULT now(),
    -- Set when the same name later resolves. Kept rather than deleted so the
    -- history shows which aliases were needed and when.
    resolved_at timestamptz,
    -- Set when this row has been alerted on. Separate from resolved_at: a row
    -- is alerted once and stays open until someone fixes it.
    notified_at timestamptz,
    CONSTRAINT ingest_failures_kind_check CHECK (kind IN ('team', 'division', 'league', 'invalid'))
);

-- NULLS NOT DISTINCT because league is legitimately NULL (manual and
-- tournament sources send none), and two NULL-league rows for the same name
-- are the same problem, not two.
CREATE UNIQUE INDEX IF NOT EXISTS ingest_failures_identity
    ON public.ingest_failures (kind, lower(raw_name), league, source) NULLS NOT DISTINCT;

CREATE INDEX IF NOT EXISTS ingest_failures_open_idx
    ON public.ingest_failures (last_seen DESC) WHERE resolved_at IS NULL;

COMMENT ON TABLE public.ingest_failures IS
    'Names the match ingest could not resolve. One row per distinct name; match_count is how many matches it cost.';
COMMENT ON COLUMN public.ingest_failures.league IS
    'League name as the feed spelled it — not a FK, because an unmapped competition name is itself the finding.';

ALTER TABLE public.ingest_failures ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: this is admin/operator data read through the backend's
-- service key, not something anon should enumerate.

-- Recording has to be atomic — a season load runs many workers concurrently
-- against the same handful of bad names, and a read-modify-write from the
-- application would lose counts. Done as a function so the DAO is one call.
-- Dropped first: CREATE OR REPLACE cannot change a function's OUT
-- parameters, so replacing the return shape in a later migration would
-- fail on any database that already has the old one.
DROP FUNCTION IF EXISTS public.record_ingest_failure(text, text, text, text, text);
CREATE FUNCTION public.record_ingest_failure(
    p_kind text,
    p_raw_name text,
    p_league text,
    p_source text,
    p_sample text
) RETURNS TABLE (id integer, match_count integer, should_alert boolean)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    INSERT INTO public.ingest_failures AS f (kind, raw_name, league, source, sample)
    VALUES (p_kind, p_raw_name, p_league, COALESCE(p_source, 'match-scraper'), p_sample)
    ON CONFLICT (kind, lower(raw_name), league, source) DO UPDATE
        -- A name that was fixed and then starts failing again is a NEW
        -- episode, not a continuation: the count restarts, and notified_at
        -- clears so it can be alerted on again. A regression that alerted
        -- once a year ago and never again is the silence this table exists
        -- to end.
        SET match_count = CASE WHEN f.resolved_at IS NOT NULL THEN 1 ELSE f.match_count + 1 END,
            first_seen  = CASE WHEN f.resolved_at IS NOT NULL THEN now() ELSE f.first_seen END,
            notified_at = CASE WHEN f.resolved_at IS NOT NULL THEN NULL ELSE f.notified_at END,
            last_seen   = now(),
            sample      = COALESCE(p_sample, f.sample),
            resolved_at = NULL
    -- "Worth alerting on" is not "first ever sighting" — it is "not yet
    -- announced". Those differ exactly in the regression case above.
    --
    -- The caller stamps notified_at only after Telegram accepts the message,
    -- so several workers hitting the same brand-new name in the same instant
    -- can each be told to alert. That is a handful of duplicate messages,
    -- bounded by worker concurrency; claiming the alert here instead would
    -- silence the name permanently if the send then failed. Duplicated beats
    -- silent, which is the whole premise of this table.
    RETURNING f.id, f.match_count, (f.notified_at IS NULL);
END;
$$;

-- Called when a name that previously failed resolves. Idempotent and cheap
-- enough to call on every successful ingest.
DROP FUNCTION IF EXISTS public.resolve_ingest_failures(text, text, text);
CREATE FUNCTION public.resolve_ingest_failures(
    p_kind text,
    p_raw_name text,
    p_source text
) RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    n integer;
BEGIN
    UPDATE public.ingest_failures
       SET resolved_at = now()
     WHERE kind = p_kind
       AND lower(raw_name) = lower(p_raw_name)
       AND source = COALESCE(p_source, 'match-scraper')
       AND resolved_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.record_ingest_failure(text, text, text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.resolve_ingest_failures(text, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_ingest_failure(text, text, text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.resolve_ingest_failures(text, text, text) TO service_role;
