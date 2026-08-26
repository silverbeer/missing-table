-- Let a person close an ingest failure that was fixed at the sender (SB-845)
--
-- resolve_ingest_failures() closes a row when the SAME raw_name later
-- resolves, which covers the case it was built for: add an alias mid-load and
-- the alert clears itself. It cannot cover the other case. When the fix is to
-- stop *sending* the bad name rather than to teach MT about it, that string is
-- never submitted again, so nothing ever triggers the resolve and the row
-- stays open forever.
--
-- That is not cosmetic. Open rows are folded into the scraper's run report
-- (SB-831), so every future run would list a problem that no longer exists,
-- and matches_dropped would drift upward from reality. A permanent false
-- positive in an alerting surface is how people learn to ignore that surface.
--
-- Resolving still does not delete. The row is the record of which names were
-- wrong and when, and that history is most of what makes this table worth
-- having — so the two columns below record who decided and why, rather than
-- the row disappearing.

ALTER TABLE public.ingest_failures
    ADD COLUMN IF NOT EXISTS resolved_by uuid,
    ADD COLUMN IF NOT EXISTS resolution_note text;

COMMENT ON COLUMN public.ingest_failures.resolved_by IS
    'Who closed this row by hand. NULL when it closed itself — the name resolved on a later ingest.';
COMMENT ON COLUMN public.ingest_failures.resolution_note IS
    'Why it was closed by hand. "Fixed at the sender" and "not a real team" are different outcomes and the table should say which.';
