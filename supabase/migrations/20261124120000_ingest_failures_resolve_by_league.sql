-- Close an ingest failure for one league only (SB-1748)
--
-- resolve_ingest_failures() closes every open row for a name, whatever its
-- league. That was right while a name meant one team. A tournament puts the
-- Homegrown and Academy sides in one event, a club's two teams share a name,
-- and each side's failure is its own row (league is part of the identity
-- index). With the league-blind close, 'AC River' resolving for Homegrown
-- closed the open Academy row; the next Academy failure reopened it as a new
-- episode — notified_at cleared — and alerted again. One alert per flap, for
-- every name that exists on one side only.
--
-- This variant closes the row for the league the message named. NULL matches
-- only rows recorded with no league, the way the identity index treats them
-- (NULLS NOT DISTINCT). resolve_ingest_failures() is unchanged and still what
-- league messages call.
--
-- Function only: no table, no column, so nothing for the backup registries.
-- Dropped first, as its siblings are, so a later change to the return shape
-- does not fail on a database that already has this one.
DROP FUNCTION IF EXISTS public.resolve_ingest_failures_by_league(text, text, text, text);
CREATE FUNCTION public.resolve_ingest_failures_by_league(
    p_kind text,
    p_raw_name text,
    p_league text,
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
       AND league IS NOT DISTINCT FROM p_league
       AND source = COALESCE(p_source, 'match-scraper')
       AND resolved_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.resolve_ingest_failures_by_league(text, text, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.resolve_ingest_failures_by_league(text, text, text, text) TO service_role;
