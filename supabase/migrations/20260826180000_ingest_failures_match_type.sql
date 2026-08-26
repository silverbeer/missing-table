-- Let an unresolvable competition be recorded like an unresolvable division (SB-847)
--
-- ingest_failures.kind was constrained to team/division/league/invalid. The
-- feed also names a competition per match ("League", "MLS NEXT Flex"), and
-- until now an unknown one was not reported at all — it was not even resolved.
-- Every scraped match was created as match_type_id 1, which is how 68 Flex
-- fixtures were filed as League in prod (SB-846).
--
-- With the competition resolved, an unknown name has to go somewhere. The
-- division precedent is the right one: fail the match loudly and record the
-- name once with a count, rather than write a plausible default and let it
-- look correct.

ALTER TABLE public.ingest_failures
    DROP CONSTRAINT IF EXISTS ingest_failures_kind_check;

ALTER TABLE public.ingest_failures
    ADD CONSTRAINT ingest_failures_kind_check
    CHECK (kind IN ('team', 'division', 'league', 'match_type', 'invalid'));
