-- QoP rankings redesign: snapshot-centric model.
--
-- Problem: the original table keyed on (week_of, division_id, age_group_id, rank),
-- so any re-scrape within the same ISO week upserted onto existing rows and
-- destroyed per-scrape history. We also had no way to represent "scraper ran
-- but data was unchanged" — every POST wrote.
--
-- New model:
--   * qop_snapshots — one row per distinct scrape that saw new data. Keyed
--     by (detected_at, division_id, age_group_id). detected_at is the date
--     the scraper first observed this particular ranking set, i.e., write
--     cadence is driven by change detection, not by a wall-clock week.
--   * qop_rankings — one row per team per snapshot (22 rows per snapshot for
--     a full U14 Northeast ingest). FK → qop_snapshots with ON DELETE CASCADE
--     so a bad scrape can be wiped atomically.
--
-- Backward data: existing qop_rankings rows are collapsed into synthetic
-- snapshots (one per distinct (week_of, division, age_group) group) preserving
-- the original scraped_at timestamp and using MAX(scraped_at)::date — i.e. the
-- date of the most recent write for that group — as detected_at.

BEGIN;

-- 1. New parent table: one row per scrape that saw new data.
CREATE TABLE qop_snapshots (
    id SERIAL PRIMARY KEY,
    detected_at DATE NOT NULL,
    division_id INTEGER NOT NULL REFERENCES divisions(id),
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id),
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'cronjob',
    UNIQUE (detected_at, division_id, age_group_id)
);

CREATE INDEX idx_qop_snapshots_latest
    ON qop_snapshots (division_id, age_group_id, detected_at DESC);

ALTER TABLE qop_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "qop_snapshots_select" ON qop_snapshots
    FOR SELECT USING (true);

-- 2. Add the FK column to qop_rankings (nullable until backfill completes).
ALTER TABLE qop_rankings
    ADD COLUMN snapshot_id INTEGER REFERENCES qop_snapshots(id) ON DELETE CASCADE;

-- 3. Backfill: one synthetic snapshot per distinct
--    (week_of, division_id, age_group_id) grouping, then repoint rankings.
DO $$
DECLARE
    rec RECORD;
    snap_id INT;
BEGIN
    FOR rec IN
        SELECT
            week_of,
            division_id,
            age_group_id,
            MAX(scraped_at) AS max_scraped_at
        FROM qop_rankings
        GROUP BY week_of, division_id, age_group_id
    LOOP
        INSERT INTO qop_snapshots (detected_at, division_id, age_group_id, scraped_at, source)
        VALUES (
            COALESCE(rec.max_scraped_at::date, rec.week_of),
            rec.division_id,
            rec.age_group_id,
            COALESCE(rec.max_scraped_at, (rec.week_of::text || ' 12:00:00+00')::timestamptz),
            'migrated'
        )
        RETURNING id INTO snap_id;

        UPDATE qop_rankings
           SET snapshot_id = snap_id
         WHERE week_of = rec.week_of
           AND division_id = rec.division_id
           AND age_group_id = rec.age_group_id;
    END LOOP;
END $$;

-- 4. Lock in the backfill.
ALTER TABLE qop_rankings ALTER COLUMN snapshot_id SET NOT NULL;

-- 5. Drop the old unique key (keyed on rank) and lookup index — the snapshot
--    FK now provides identity.
ALTER TABLE qop_rankings
    DROP CONSTRAINT IF EXISTS qop_rankings_week_of_division_id_age_group_id_rank_key;
DROP INDEX IF EXISTS idx_qop_rankings_lookup;

-- 6. Drop columns that moved to the snapshot row.
ALTER TABLE qop_rankings DROP COLUMN week_of;
ALTER TABLE qop_rankings DROP COLUMN division_id;
ALTER TABLE qop_rankings DROP COLUMN age_group_id;
ALTER TABLE qop_rankings DROP COLUMN scraped_at;

-- 7. New identity constraints: rank is unique within a snapshot, and a team
--    name appears at most once per snapshot (defensive — mlssoccer shouldn't
--    list the same club twice, but guard against scraper bugs).
ALTER TABLE qop_rankings
    ADD CONSTRAINT qop_rankings_snapshot_rank_key UNIQUE (snapshot_id, rank);
ALTER TABLE qop_rankings
    ADD CONSTRAINT qop_rankings_snapshot_team_key UNIQUE (snapshot_id, team_name);

CREATE INDEX idx_qop_rankings_snapshot ON qop_rankings (snapshot_id);

COMMIT;
