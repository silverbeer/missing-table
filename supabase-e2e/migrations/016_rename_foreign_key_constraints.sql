-- Rename foreign key constraints to match new table names
-- This fixes PostgREST relationship detection

-- Rename foreign key constraints on matches table
DO $$
BEGIN
    -- Rename home_team_id foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_home_team_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_home_team_id_fkey TO matches_home_team_id_fkey;
        RAISE NOTICE 'Renamed games_home_team_id_fkey to matches_home_team_id_fkey';
    END IF;

    -- Rename away_team_id foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_away_team_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_away_team_id_fkey TO matches_away_team_id_fkey;
        RAISE NOTICE 'Renamed games_away_team_id_fkey to matches_away_team_id_fkey';
    END IF;

    -- Rename season_id foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_season_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_season_id_fkey TO matches_season_id_fkey;
        RAISE NOTICE 'Renamed games_season_id_fkey to matches_season_id_fkey';
    END IF;

    -- Rename age_group_id foreign key
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_age_group_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_age_group_id_fkey TO matches_age_group_id_fkey;
        RAISE NOTICE 'Renamed games_age_group_id_fkey to matches_age_group_id_fkey';
    END IF;

    -- Rename game_type_id foreign key (should be match_type_id now)
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_game_type_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_game_type_id_fkey TO matches_match_type_id_fkey;
        RAISE NOTICE 'Renamed games_game_type_id_fkey to matches_match_type_id_fkey';
    END IF;

    -- Rename division_id foreign key (if it exists)
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'matches' AND constraint_name = 'games_division_id_fkey'
    ) THEN
        ALTER TABLE matches RENAME CONSTRAINT games_division_id_fkey TO matches_division_id_fkey;
        RAISE NOTICE 'Renamed games_division_id_fkey to matches_division_id_fkey';
    END IF;

    RAISE NOTICE '=================================================================';
    RAISE NOTICE 'Foreign key constraints renamed successfully!';
    RAISE NOTICE 'PostgREST should now properly detect relationships.';
    RAISE NOTICE '=================================================================';
END $$;
