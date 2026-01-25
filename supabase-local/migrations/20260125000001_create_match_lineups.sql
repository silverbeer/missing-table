-- Migration: Create match_lineups table for storing team lineups/formations
-- Stores formation name and player-position assignments per team per match

CREATE TABLE IF NOT EXISTS match_lineups (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    formation_name VARCHAR(20) NOT NULL DEFAULT '4-3-3',
    positions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    UNIQUE(match_id, team_id)
);

-- Index for efficient match lookups
CREATE INDEX IF NOT EXISTS idx_match_lineups_match_id ON match_lineups(match_id);

-- Comments
COMMENT ON TABLE match_lineups IS 'Team lineups for matches - stores formation and player-position assignments';
COMMENT ON COLUMN match_lineups.formation_name IS 'Formation preset name (e.g., 4-3-3, 4-4-2, 3-5-2)';
COMMENT ON COLUMN match_lineups.positions IS 'JSONB array of {player_id, position} objects';

-- Trigger function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_match_lineups_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Create trigger
DROP TRIGGER IF EXISTS match_lineups_update_timestamp ON match_lineups;
CREATE TRIGGER match_lineups_update_timestamp
    BEFORE UPDATE ON match_lineups
    FOR EACH ROW
    EXECUTE FUNCTION update_match_lineups_updated_at();

-- RLS Policies
ALTER TABLE match_lineups ENABLE ROW LEVEL SECURITY;

-- Everyone can read lineups
CREATE POLICY match_lineups_select_policy ON match_lineups
    FOR SELECT
    USING (true);

-- Authenticated users can insert lineups
CREATE POLICY match_lineups_insert_policy ON match_lineups
    FOR INSERT
    WITH CHECK (true);

-- Authenticated users can update lineups
CREATE POLICY match_lineups_update_policy ON match_lineups
    FOR UPDATE
    USING (true);

-- Enable realtime for this table
ALTER PUBLICATION supabase_realtime ADD TABLE match_lineups;
