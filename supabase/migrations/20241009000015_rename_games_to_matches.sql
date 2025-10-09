-- Comprehensive migration to rename games to matches for consistency and clarity
-- This migration renames tables, columns, indexes, constraints, and comments
-- to reflect "match" terminology throughout the application

-- ============================================================================
-- STEP 1: Rename enum type (if exists)
-- ============================================================================

-- Rename game_status enum to match_status (only if it exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'game_status') THEN
        ALTER TYPE game_status RENAME TO match_status;
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Rename tables (if they exist)
-- ============================================================================

-- Rename main games table to matches
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'games') THEN
        ALTER TABLE games RENAME TO matches;
    END IF;
END $$;

-- Rename game_types table to match_types
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'game_types') THEN
        ALTER TABLE game_types RENAME TO match_types;
    END IF;
END $$;

-- Rename team_game_types table to team_match_types (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'team_game_types') THEN
        ALTER TABLE team_game_types RENAME TO team_match_types;
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Rename columns in matches table
-- ============================================================================

-- Rename game_date to match_date
ALTER TABLE matches RENAME COLUMN game_date TO match_date;

-- ============================================================================
-- STEP 4: Rename foreign key columns (if they exist)
-- ============================================================================

-- Rename game_type_id to match_type_id in matches table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'matches' AND column_name = 'game_type_id') THEN
        ALTER TABLE matches RENAME COLUMN game_type_id TO match_type_id;
    END IF;
END $$;

-- Rename game_type_id to match_type_id in team_match_types table (if table and column exist)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'team_match_types' AND column_name = 'game_type_id') THEN
        ALTER TABLE team_match_types RENAME COLUMN game_type_id TO match_type_id;
    END IF;
END $$;

-- ============================================================================
-- STEP 5: Rename indexes (only if they exist)
-- ============================================================================

-- Helper function to rename index if it exists
DO $$
DECLARE
    idx_record RECORD;
    old_names TEXT[] := ARRAY[
        'idx_games_date', 'idx_games_home_team', 'idx_games_away_team',
        'idx_games_season', 'idx_games_age_group', 'idx_games_division',
        'idx_games_mls_match_id', 'idx_games_data_source', 'idx_games_mls_match_id_unique',
        'idx_games_status', 'idx_games_status_filters', 'idx_games_match_id',
        'idx_games_unique_match', 'idx_games_unique_external_match',
        'idx_team_game_types_team', 'idx_team_game_types_game_type',
        'idx_team_game_types_age_group', 'idx_team_game_types_active'
    ];
    new_names TEXT[] := ARRAY[
        'idx_matches_date', 'idx_matches_home_team', 'idx_matches_away_team',
        'idx_matches_season', 'idx_matches_age_group', 'idx_matches_division',
        'idx_matches_mls_match_id', 'idx_matches_data_source', 'idx_matches_mls_match_id_unique',
        'idx_matches_status', 'idx_matches_status_filters', 'idx_matches_match_id',
        'idx_matches_unique_match', 'idx_matches_unique_external_match',
        'idx_team_match_types_team', 'idx_team_match_types_match_type',
        'idx_team_match_types_age_group', 'idx_team_match_types_active'
    ];
BEGIN
    FOR i IN 1..array_length(old_names, 1) LOOP
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = old_names[i]) THEN
            EXECUTE format('ALTER INDEX %I RENAME TO %I', old_names[i], new_names[i]);
            RAISE NOTICE 'Renamed index % to %', old_names[i], new_names[i];
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- STEP 6: Rename constraints (only if they exist)
-- ============================================================================

-- Rename check constraint on matches table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_schema = 'public'
               AND table_name = 'matches'
               AND constraint_name = 'chk_games_data_source') THEN
        ALTER TABLE matches RENAME CONSTRAINT chk_games_data_source TO chk_matches_data_source;
    END IF;
END $$;

-- ============================================================================
-- STEP 7: Update comments to reflect new terminology (only where applicable)
-- ============================================================================

-- Update enum type comment (only if type exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'match_status') THEN
        EXECUTE 'COMMENT ON TYPE match_status IS ''Enum for tracking match states throughout their lifecycle''';
    END IF;
END $$;

-- Update matches table comments (only for columns that exist)
DO $$
BEGIN
    -- Only add comments for columns that exist
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
END $$;

-- Update index comments (only for indexes that exist)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_matches_status') THEN
        EXECUTE 'COMMENT ON INDEX idx_matches_status IS ''Index for filtering matches by status (performance optimization for standings)''';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_matches_status_filters') THEN
        EXECUTE 'COMMENT ON INDEX idx_matches_status_filters IS ''Composite index for common status + filter queries''';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_matches_unique_match') THEN
        EXECUTE 'COMMENT ON INDEX idx_matches_unique_match IS ''Prevents duplicate matches for the same teams, date, season, age group, and match type''';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_matches_unique_external_match') THEN
        EXECUTE 'COMMENT ON INDEX idx_matches_unique_external_match IS ''Ensures external match IDs are unique across the system''';
    END IF;
END $$;

-- Add table-level comments for documentation (only for tables that exist)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'matches') THEN
        COMMENT ON TABLE matches IS 'Stores match records including scores, dates, and status. Renamed from games for consistency.';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'match_types') THEN
        COMMENT ON TABLE match_types IS 'Defines types of matches (League, Tournament, Friendly, Playoff). Renamed from game_types for consistency.';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'team_match_types') THEN
        COMMENT ON TABLE team_match_types IS 'Maps teams to match types they participate in for each age group. Renamed from team_game_types for consistency.';
    END IF;
END $$;

-- ============================================================================
-- STEP 8: Update constraint comments
-- ============================================================================

COMMENT ON CONSTRAINT chk_matches_data_source ON matches IS 'Ensures data_source is either manual or mls_scraper';
