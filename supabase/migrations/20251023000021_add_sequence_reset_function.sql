-- Migration: Add helper function to reset all table sequences
-- Created: 2025-10-23
-- Purpose: Prevents "duplicate key" errors after data restoration by ensuring
--          all PostgreSQL sequences are synchronized with the actual max IDs in tables

-- =====================================================================
-- Function: reset_all_sequences()
-- =====================================================================
-- This function finds all tables with SERIAL/BIGSERIAL columns and resets
-- their sequences to MAX(id) + 1. This is critical after:
-- - Restoring data from backups
-- - Importing data with explicit IDs
-- - Migrating data from other systems
--
-- Usage:
--   SELECT reset_all_sequences();
--
-- Returns: Number of sequences that were reset
-- =====================================================================

CREATE OR REPLACE FUNCTION reset_all_sequences()
RETURNS INTEGER AS $$
DECLARE
    seq_record RECORD;
    sequences_reset INTEGER := 0;
    max_value BIGINT;
    current_value BIGINT;
BEGIN
    -- Loop through all columns that use sequences (SERIAL/BIGSERIAL)
    FOR seq_record IN
        SELECT
            c.table_name::text,
            c.column_name::text,
            pg_get_serial_sequence(c.table_name::text, c.column_name::text) as sequence_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        AND c.column_default LIKE 'nextval%'
        AND pg_get_serial_sequence(c.table_name::text, c.column_name::text) IS NOT NULL
        ORDER BY c.table_name, c.column_name
    LOOP
        -- Get the maximum ID value from the table
        EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I',
            seq_record.column_name,
            seq_record.table_name)
        INTO max_value;

        -- Get the current sequence value
        EXECUTE format('SELECT last_value FROM %s', seq_record.sequence_name)
        INTO current_value;

        -- Only reset if the max value is greater than current sequence value
        IF max_value > current_value THEN
            -- Reset the sequence to max_value + 1
            EXECUTE format('SELECT setval(%L, %s, true)',
                seq_record.sequence_name,
                max_value
            );

            sequences_reset := sequences_reset + 1;

            RAISE NOTICE 'Reset sequence for %.%: % → %',
                seq_record.table_name,
                seq_record.column_name,
                current_value,
                max_value;
        ELSE
            RAISE NOTICE 'Skipped %.%: sequence (%s) already ahead of max (%s)',
                seq_record.table_name,
                seq_record.column_name,
                current_value,
                max_value;
        END IF;
    END LOOP;

    RETURN sequences_reset;
END;
$$ LANGUAGE plpgsql;

-- Add helpful comment to the function
COMMENT ON FUNCTION reset_all_sequences() IS
'Resets all PostgreSQL sequences to match the maximum ID values in their tables.
Run this after restoring data from backups to prevent duplicate key violations.';

-- =====================================================================
-- Run the function immediately to fix any existing sequence issues
-- Only run if tables exist (skip on fresh install)
-- =====================================================================
DO $$
DECLARE
    reset_count INTEGER;
    tables_exist BOOLEAN;
BEGIN
    -- Check if any tables exist in public schema
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        LIMIT 1
    ) INTO tables_exist;

    IF tables_exist THEN
        SELECT reset_all_sequences() INTO reset_count;
        RAISE NOTICE 'Migration complete: Reset % sequence(s)', reset_count;
    ELSE
        RAISE NOTICE 'Skipping sequence reset: No tables exist yet';
    END IF;
END $$;
