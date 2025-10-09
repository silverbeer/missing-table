-- Comprehensive migration to rename games to matches for consistency and clarity
-- This migration renames tables, columns, indexes, constraints, and comments
-- SAFE VERSION: Checks for existence before renaming

-- ============================================================================
-- STEP 1: Rename enum type (if it exists)
-- ============================================================================

-- Rename game_status enum to match_status (only if it exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'game_status') THEN
        ALTER TYPE game_status RENAME TO match_status;
        RAISE NOTICE 'Renamed game_status enum to match_status';
    ELSE
        RAISE NOTICE 'game_status enum does not exist, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Rename tables
-- ============================================================================

-- Rename main games table to matches
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'games') THEN
        ALTER TABLE games RENAME TO matches;
        RAISE NOTICE 'Renamed games table to matches';
    ELSE
        RAISE NOTICE 'games table does not exist, skipping';
    END IF;
END $$;

-- Rename game_types table to match_types
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'game_types') THEN
        ALTER TABLE game_types RENAME TO match_types;
        RAISE NOTICE 'Renamed game_types table to match_types';
    ELSE
        RAISE NOTICE 'game_types table does not exist, skipping';
    END IF;
END $$;

-- Rename team_game_types table to team_match_types
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'team_game_types') THEN
        ALTER TABLE team_game_types RENAME TO team_match_types;
        RAISE NOTICE 'Renamed team_game_types table to team_match_types';
    ELSE
        RAISE NOTICE 'team_game_types table does not exist, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Rename columns in matches table
-- ============================================================================

-- Rename game_date to match_date
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'game_date'
    ) THEN
        ALTER TABLE matches RENAME COLUMN game_date TO match_date;
        RAISE NOTICE 'Renamed game_date column to match_date';
    ELSE
        RAISE NOTICE 'game_date column does not exist in matches table, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Rename foreign key columns
-- ============================================================================

-- Rename game_type_id to match_type_id in matches table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'game_type_id'
    ) THEN
        ALTER TABLE matches RENAME COLUMN game_type_id TO match_type_id;
        RAISE NOTICE 'Renamed game_type_id column to match_type_id in matches table';
    ELSE
        RAISE NOTICE 'game_type_id column does not exist in matches table, skipping';
    END IF;
END $$;

-- Rename game_type_id to match_type_id in team_match_types table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'team_match_types' AND column_name = 'game_type_id'
    ) THEN
        ALTER TABLE team_match_types RENAME COLUMN game_type_id TO match_type_id;
        RAISE NOTICE 'Renamed game_type_id column to match_type_id in team_match_types table';
    ELSE
        RAISE NOTICE 'game_type_id column does not exist in team_match_types table, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 5: Rename indexes (with existence checks)
-- ============================================================================

-- Helper function to safely rename index
DO $$
DECLARE
    idx_record RECORD;
BEGIN
    -- Indexes on matches table
    FOR idx_record IN
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'matches' AND indexname LIKE 'idx_games_%'
    LOOP
        EXECUTE format('ALTER INDEX %I RENAME TO %I',
            idx_record.indexname,
            replace(idx_record.indexname, 'idx_games_', 'idx_matches_'));
        RAISE NOTICE 'Renamed index: % to %',
            idx_record.indexname,
            replace(idx_record.indexname, 'idx_games_', 'idx_matches_');
    END LOOP;

    -- Indexes on team_match_types table
    FOR idx_record IN
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'team_match_types' AND indexname LIKE 'idx_team_game_types_%'
    LOOP
        EXECUTE format('ALTER INDEX %I RENAME TO %I',
            idx_record.indexname,
            replace(replace(idx_record.indexname, 'idx_team_game_types_', 'idx_team_match_types_'), '_game_type', '_match_type'));
        RAISE NOTICE 'Renamed index: % to %',
            idx_record.indexname,
            replace(replace(idx_record.indexname, 'idx_team_game_types_', 'idx_team_match_types_'), '_game_type', '_match_type');
    END LOOP;

    -- Handle primary key constraint name
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'games_pkey') THEN
        ALTER INDEX games_pkey RENAME TO matches_pkey;
        RAISE NOTICE 'Renamed games_pkey to matches_pkey';
    END IF;
END $$;

-- ============================================================================
-- STEP 6: Rename constraints
-- ============================================================================

-- Rename check constraint on matches table
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'chk_games_data_source'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT chk_games_data_source TO chk_matches_data_source;
        RAISE NOTICE 'Renamed chk_games_data_source constraint to chk_matches_data_source';
    ELSE
        RAISE NOTICE 'chk_games_data_source constraint does not exist, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 7: Update comments to reflect new terminology
-- ============================================================================

-- Update enum type comment (if it exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'match_status') THEN
        COMMENT ON TYPE match_status IS 'Enum for tracking match states throughout their lifecycle';
        RAISE NOTICE 'Updated match_status enum comment';
    END IF;
END $$;

-- Update matches table comments
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'matches') THEN
        COMMENT ON TABLE matches IS 'Stores match records including scores, dates, and status. Renamed from games for consistency.';

        -- Update column comments if they exist
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'mls_match_id') THEN
            COMMENT ON COLUMN matches.mls_match_id IS 'MLS Next match identifier for scraped matches (e.g., 98667)';
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'data_source') THEN
            COMMENT ON COLUMN matches.data_source IS 'Source of match data: manual (team admin) or mls_scraper';
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'last_scraped_at') THEN
            COMMENT ON COLUMN matches.last_scraped_at IS 'Timestamp when scraper last updated this match';
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'score_locked') THEN
            COMMENT ON COLUMN matches.score_locked IS 'Prevents scraper from overwriting manually entered scores';
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'status') THEN
            COMMENT ON COLUMN matches.status IS 'Current status of the match: scheduled (future), played (completed), postponed (delayed), cancelled (not happening)';
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'matches' AND column_name = 'match_id') THEN
            COMMENT ON COLUMN matches.match_id IS 'External match identifier from systems like match-scraper. NULL for manually created matches.';
        END IF;

        RAISE NOTICE 'Updated matches table comments';
    END IF;
END $$;

-- Update match_types table comment
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'match_types') THEN
        COMMENT ON TABLE match_types IS 'Defines types of matches (League, Tournament, Friendly, Playoff). Renamed from game_types for consistency.';
        RAISE NOTICE 'Updated match_types table comment';
    END IF;
END $$;

-- Update team_match_types table comment
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'team_match_types') THEN
        COMMENT ON TABLE team_match_types IS 'Maps teams to match types they participate in for each age group. Renamed from team_game_types for consistency.';
        RAISE NOTICE 'Updated team_match_types table comment';
    END IF;
END $$;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '=================================================================';
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Tables renamed: games → matches, game_types → match_types';
    RAISE NOTICE 'Columns renamed: game_date → match_date, game_type_id → match_type_id';
    RAISE NOTICE '=================================================================';
END $$;
