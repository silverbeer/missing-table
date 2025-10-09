-- Comprehensive migration to rename games to matches for consistency and clarity
-- This migration renames tables, columns, indexes, constraints, and comments
-- to reflect "match" terminology throughout the application

-- ============================================================================
-- STEP 1: Rename enum type
-- ============================================================================

-- Rename game_status enum to match_status
ALTER TYPE game_status RENAME TO match_status;

-- ============================================================================
-- STEP 2: Rename tables
-- ============================================================================

-- Rename main games table to matches
ALTER TABLE games RENAME TO matches;

-- Rename game_types table to match_types
ALTER TABLE game_types RENAME TO match_types;

-- Rename team_game_types table to team_match_types
ALTER TABLE team_game_types RENAME TO team_match_types;

-- ============================================================================
-- STEP 3: Rename columns in matches table
-- ============================================================================

-- Rename game_date to match_date
ALTER TABLE matches RENAME COLUMN game_date TO match_date;

-- ============================================================================
-- STEP 4: Rename foreign key columns
-- ============================================================================

-- Rename game_type_id to match_type_id in matches table
ALTER TABLE matches RENAME COLUMN game_type_id TO match_type_id;

-- Rename game_type_id to match_type_id in team_match_types table
ALTER TABLE team_match_types RENAME COLUMN game_type_id TO match_type_id;

-- ============================================================================
-- STEP 5: Rename indexes
-- ============================================================================

-- Indexes on matches table (formerly games)
ALTER INDEX idx_games_date RENAME TO idx_matches_date;
ALTER INDEX idx_games_home_team RENAME TO idx_matches_home_team;
ALTER INDEX idx_games_away_team RENAME TO idx_matches_away_team;
ALTER INDEX idx_games_season RENAME TO idx_matches_season;
ALTER INDEX idx_games_age_group RENAME TO idx_matches_age_group;
ALTER INDEX idx_games_division RENAME TO idx_matches_division;
ALTER INDEX idx_games_mls_match_id RENAME TO idx_matches_mls_match_id;
ALTER INDEX idx_games_data_source RENAME TO idx_matches_data_source;
ALTER INDEX idx_games_mls_match_id_unique RENAME TO idx_matches_mls_match_id_unique;
ALTER INDEX idx_games_status RENAME TO idx_matches_status;
ALTER INDEX idx_games_status_filters RENAME TO idx_matches_status_filters;
ALTER INDEX idx_games_match_id RENAME TO idx_matches_match_id;
ALTER INDEX idx_games_unique_match RENAME TO idx_matches_unique_match;
ALTER INDEX idx_games_unique_external_match RENAME TO idx_matches_unique_external_match;

-- Indexes on team_match_types table (formerly team_game_types)
ALTER INDEX idx_team_game_types_team RENAME TO idx_team_match_types_team;
ALTER INDEX idx_team_game_types_game_type RENAME TO idx_team_match_types_match_type;
ALTER INDEX idx_team_game_types_age_group RENAME TO idx_team_match_types_age_group;
ALTER INDEX idx_team_game_types_active RENAME TO idx_team_match_types_active;

-- ============================================================================
-- STEP 6: Rename constraints
-- ============================================================================

-- Rename check constraint on matches table
ALTER TABLE matches RENAME CONSTRAINT chk_games_data_source TO chk_matches_data_source;

-- ============================================================================
-- STEP 7: Update comments to reflect new terminology
-- ============================================================================

-- Update enum type comment
COMMENT ON TYPE match_status IS 'Enum for tracking match states throughout their lifecycle';

-- Update matches table comments
COMMENT ON COLUMN matches.mls_match_id IS 'MLS Next match identifier for scraped matches (e.g., 98667)';
COMMENT ON COLUMN matches.data_source IS 'Source of match data: manual (team admin) or mls_scraper';
COMMENT ON COLUMN matches.last_scraped_at IS 'Timestamp when scraper last updated this match';
COMMENT ON COLUMN matches.score_locked IS 'Prevents scraper from overwriting manually entered scores';
COMMENT ON COLUMN matches.status IS 'Current status of the match: scheduled (future), played (completed), postponed (delayed), cancelled (not happening)';
COMMENT ON COLUMN matches.match_id IS 'External match identifier from systems like match-scraper. NULL for manually created matches.';

-- Update index comments
COMMENT ON INDEX idx_matches_status IS 'Index for filtering matches by status (performance optimization for standings)';
COMMENT ON INDEX idx_matches_status_filters IS 'Composite index for common status + filter queries';
COMMENT ON INDEX idx_matches_unique_match IS 'Prevents duplicate matches for the same teams, date, season, age group, match type, and division';
COMMENT ON INDEX idx_matches_unique_external_match IS 'Ensures external match IDs are unique across the system';

-- Add table-level comments for documentation
COMMENT ON TABLE matches IS 'Stores match records including scores, dates, and status. Renamed from games for consistency.';
COMMENT ON TABLE match_types IS 'Defines types of matches (League, Tournament, Friendly, Playoff). Renamed from game_types for consistency.';
COMMENT ON TABLE team_match_types IS 'Maps teams to match types they participate in for each age group. Renamed from team_game_types for consistency.';

-- ============================================================================
-- STEP 8: Update constraint comments
-- ============================================================================

COMMENT ON CONSTRAINT chk_matches_data_source ON matches IS 'Ensures data_source is either manual or mls_scraper';
