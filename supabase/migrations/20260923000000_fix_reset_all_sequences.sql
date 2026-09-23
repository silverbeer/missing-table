-- Fix reset_all_sequences(): honour is_called, and qualify identifiers by schema.
--
-- SB-26. The previous version guarded the reset with:
--
--     IF max_value > current_value THEN ... setval(seq, max_value, true)
--
-- where current_value came from `SELECT last_value FROM <seq>`. That reads only
-- half the sequence state. A sequence carries (last_value, is_called), and the
-- next value nextval() issues is:
--
--     is_called = true   ->  last_value + 1
--     is_called = false  ->  last_value
--
-- A restore that ends with `setval(seq, 86, false)` leaves last_value = 86 and
-- is_called = false, so nextval() returns 86 while row id = 86 already exists.
-- The guard compared 86 > 86, concluded the sequence was already ahead, and
-- skipped it — leaving the collision in place:
--
--     duplicate key value violates unique constraint "team_mappings_pkey"
--     Key (id)=(86) already exists.
--
-- The guard cannot be repaired by comparing against last_value + 1 either,
-- because that is only correct when is_called is true. Since setval is cheap
-- and idempotent, the fix drops the guard and always writes the correct state:
--
--     rows present (max > 0)  ->  setval(seq, max, true)   -> next = max + 1
--     empty table  (max = 0)  ->  setval(seq, 1,   false)  -> next = 1
--
-- The empty-table branch also fixes a second, quieter bug: the old code would
-- have issued id 2 as the first id of an empty table, silently burning id 1.
--
-- Identifiers are now schema-qualified via quote_ident. pg_get_serial_sequence
-- parses its first argument as an identifier, so an unqualified table name
-- depends on search_path and breaks on any name needing quoting.

CREATE OR REPLACE FUNCTION public.reset_all_sequences() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    seq_record RECORD;
    sequences_reset INTEGER := 0;
    max_value BIGINT;
    qualified_table TEXT;
    sequence_name TEXT;
BEGIN
    FOR seq_record IN
        SELECT
            c.table_schema::text AS table_schema,
            c.table_name::text   AS table_name,
            c.column_name::text  AS column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema
         AND t.table_name   = c.table_name
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND c.column_default LIKE 'nextval%'
        ORDER BY c.table_name, c.column_name
    LOOP
        qualified_table := quote_ident(seq_record.table_schema) || '.'
                        || quote_ident(seq_record.table_name);

        sequence_name := pg_get_serial_sequence(qualified_table, seq_record.column_name);
        CONTINUE WHEN sequence_name IS NULL;

        EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %s',
                       seq_record.column_name,
                       qualified_table)
        INTO max_value;

        -- Always write the sequence. setval is idempotent, so re-running this
        -- on an already-correct sequence is a no-op rather than a double-advance.
        EXECUTE format('SELECT setval(%L, %s, %L)',
                       sequence_name,
                       GREATEST(max_value, 1),
                       max_value > 0);

        sequences_reset := sequences_reset + 1;

        RAISE NOTICE 'Reset sequence %: next value is %',
            sequence_name,
            CASE WHEN max_value > 0 THEN max_value + 1 ELSE 1 END;
    END LOOP;

    RETURN sequences_reset;
END;
$$;

COMMENT ON FUNCTION public.reset_all_sequences() IS
'Resets every public sequence so the next id it issues is MAX(id) + 1, or 1 for an empty table.
Run after restoring data from a backup: pg_dump-style restores insert explicit ids without
advancing the sequence, and PostgREST inserts rely on DEFAULT nextval(). Always safe to re-run.';
