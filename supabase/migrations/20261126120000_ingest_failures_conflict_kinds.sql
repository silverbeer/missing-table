-- Record feed-vs-person disagreements where the unresolved names already are (SB-1787)
--
-- The ingest worker now meets two situations that are not failures to resolve
-- a name, but that an admin has to see for the same reason — a message did
-- something, or was stopped from doing something, and the only trace used to
-- be a worker log line:
--
--   score_locked             the feed sent a different score/status/home-away
--                            for a match whose score a person locked; the
--                            change was held and the row left as it was.
--   scraped_overrode_manual  the feed's score replaced one a person entered or
--                            edited. Scraped data wins on results (CLAUDE.md
--                            rule 5), but the disagreement is surfaced rather
--                            than silently resolved.
--
-- One row per match per kind (raw_name is "match <id>"), so a match re-sent
-- every night reads as one finding with a count, like a bad team name does.
-- These rows are not closed automatically: nothing on the success path can
-- tell that a person has looked. `mt ingest resolve <id>` closes one.

ALTER TABLE public.ingest_failures
    DROP CONSTRAINT IF EXISTS ingest_failures_kind_check;

ALTER TABLE public.ingest_failures
    ADD CONSTRAINT ingest_failures_kind_check
    CHECK (kind IN (
        'team', 'division', 'league', 'match_type', 'invalid',
        'score_locked', 'scraped_overrode_manual'
    ));
