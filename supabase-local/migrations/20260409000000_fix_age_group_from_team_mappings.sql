-- Fix age_group_id lookup: use team_mappings as source of truth
--
-- Context: teams.age_group_id is always NULL because add_team() writes to
-- team_mappings (many-to-many) instead. The DB function create_player_history_entry
-- and player_dao.py both read from teams.age_group_id, so player_team_history
-- records never get an age group. This migration fixes the DB function and
-- backfills all existing NULL records.

-- Step 1: Replace create_player_history_entry to read age_group_id from team_mappings
CREATE OR REPLACE FUNCTION public.create_player_history_entry(
    p_player_id uuid,
    p_team_id integer,
    p_season_id integer,
    p_jersey_number integer DEFAULT NULL::integer,
    p_positions text[] DEFAULT NULL::text[]
) RETURNS public.player_team_history
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_team RECORD;
    v_age_group_id integer;
    v_result player_team_history;
BEGIN
    -- Get team details (league_id and division_id are populated on the teams table)
    SELECT league_id, division_id INTO v_team
    FROM teams WHERE id = p_team_id;

    -- Get age_group_id from team_mappings (teams.age_group_id is deprecated/never populated)
    SELECT age_group_id INTO v_age_group_id
    FROM team_mappings WHERE team_id = p_team_id LIMIT 1;

    -- Mark any existing current entries as not current
    UPDATE player_team_history
    SET is_current = false, updated_at = NOW()
    WHERE player_id = p_player_id AND is_current = true;

    -- Insert new history entry
    INSERT INTO player_team_history (
        player_id, team_id, season_id,
        age_group_id, league_id, division_id,
        jersey_number, positions, is_current
    ) VALUES (
        p_player_id, p_team_id, p_season_id,
        v_age_group_id, v_team.league_id, v_team.division_id,
        p_jersey_number, p_positions, true
    )
    ON CONFLICT (player_id, team_id, season_id)
    DO UPDATE SET
        jersey_number = COALESCE(EXCLUDED.jersey_number, player_team_history.jersey_number),
        positions = COALESCE(EXCLUDED.positions, player_team_history.positions),
        is_current = true,
        updated_at = NOW()
    RETURNING * INTO v_result;

    RETURN v_result;
END;
$$;

-- Step 2: Backfill existing player_team_history records where age_group_id is NULL
UPDATE player_team_history pth
SET age_group_id = (
    SELECT tm.age_group_id
    FROM team_mappings tm
    WHERE tm.team_id = pth.team_id
    LIMIT 1
)
WHERE pth.age_group_id IS NULL;

-- Step 3: Deprecate the teams.age_group_id column
COMMENT ON COLUMN public.teams.age_group_id IS
    'DEPRECATED: Always NULL. Use team_mappings table for age group relationships (supports many-to-many).';
