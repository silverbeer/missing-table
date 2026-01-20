-- Migration: Create players table for roster management
-- Players can exist independent of MT accounts (user_profiles)
-- Jersey number + team + season uniquely identifies a player

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    jersey_number INTEGER NOT NULL CHECK (jersey_number >= 1 AND jersey_number <= 99),

    -- Optional name (for players without accounts, or override)
    first_name VARCHAR(100),
    last_name VARCHAR(100),

    -- Link to MT account (NULL if player has no account)
    user_profile_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,

    -- Position info (array of position codes)
    positions TEXT[],

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,

    -- Jersey number must be unique per team per season
    UNIQUE(team_id, season_id, jersey_number)
);

-- Indexes for common queries
CREATE INDEX idx_players_team_season ON players(team_id, season_id);
CREATE INDEX idx_players_user_profile ON players(user_profile_id) WHERE user_profile_id IS NOT NULL;
CREATE INDEX idx_players_active ON players(team_id, is_active) WHERE is_active = true;

-- Comments
COMMENT ON TABLE players IS 'Roster entries for teams - independent of MT accounts';
COMMENT ON COLUMN players.jersey_number IS 'Jersey number (1-99), unique per team per season';
COMMENT ON COLUMN players.user_profile_id IS 'Link to MT account (NULL if player has no account)';
COMMENT ON COLUMN players.first_name IS 'Player first name (optional, for display when no account)';
COMMENT ON COLUMN players.last_name IS 'Player last name (optional, for display when no account)';

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_players_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER players_updated_at_trigger
    BEFORE UPDATE ON players
    FOR EACH ROW
    EXECUTE FUNCTION update_players_updated_at();

-- RLS Policies
ALTER TABLE players ENABLE ROW LEVEL SECURITY;

-- Everyone can view players (roster is public)
CREATE POLICY players_select_all ON players
    FOR SELECT
    USING (true);

-- Service role can do everything
CREATE POLICY players_service_all ON players
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
