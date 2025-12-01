-- ============================================================================
-- ADD PLAYER TEAM HISTORY
-- ============================================================================
-- Purpose: Track player team assignments across seasons for year-over-year history
-- Impact: New table player_team_history, functions to manage history
-- Author: Claude Code
-- Date: 2025-12-01
-- ============================================================================

-- ============================================================================
-- PLAYER TEAM HISTORY TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS player_team_history (
    id SERIAL PRIMARY KEY,
    player_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    age_group_id INTEGER REFERENCES age_groups(id),
    league_id INTEGER REFERENCES leagues(id),
    division_id INTEGER REFERENCES divisions(id),
    jersey_number INTEGER,
    positions TEXT[],
    is_current BOOLEAN DEFAULT false,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure a player can only have one record per team per season
    UNIQUE(player_id, team_id, season_id)
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_player_team_history_player ON player_team_history(player_id);
CREATE INDEX IF NOT EXISTS idx_player_team_history_current ON player_team_history(player_id, is_current) WHERE is_current = true;
CREATE INDEX IF NOT EXISTS idx_player_team_history_season ON player_team_history(season_id);

-- ============================================================================
-- RLS POLICIES
-- ============================================================================

ALTER TABLE player_team_history ENABLE ROW LEVEL SECURITY;

-- Players can view their own history
CREATE POLICY "Players can view own history"
ON player_team_history FOR SELECT
TO authenticated
USING (player_id = auth.uid());

-- Admins and team managers can view all history
CREATE POLICY "Admins can view all history"
ON player_team_history FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM user_profiles
        WHERE id = auth.uid()
        AND role IN ('admin', 'team-manager')
    )
);

-- Service role can manage all history
CREATE POLICY "Service role can manage history"
ON player_team_history FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- ============================================================================
-- HELPER FUNCTION: Create history entry for current assignment
-- ============================================================================

CREATE OR REPLACE FUNCTION create_player_history_entry(
    p_player_id UUID,
    p_team_id INTEGER,
    p_season_id INTEGER,
    p_jersey_number INTEGER DEFAULT NULL,
    p_positions TEXT[] DEFAULT NULL
) RETURNS player_team_history AS $$
DECLARE
    v_team RECORD;
    v_result player_team_history;
BEGIN
    -- Get team details
    SELECT age_group_id, league_id, division_id INTO v_team
    FROM teams WHERE id = p_team_id;

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
        v_team.age_group_id, v_team.league_id, v_team.division_id,
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
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- UPDATE SCHEMA VERSION
-- ============================================================================

SELECT add_schema_version(
    '1.6.0',
    '20251201000001_add_player_team_history',
    'Add player team history table for tracking year-over-year assignments'
);
