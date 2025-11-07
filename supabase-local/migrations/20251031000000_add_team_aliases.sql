-- Add team_aliases table for mapping external team names to internal teams by league
-- This allows teams to have different names on external sites (like mlssoccer.com)
-- while maintaining separate team entities for different leagues

CREATE TABLE team_aliases (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
    external_name VARCHAR(255) NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'mlssoccer.com',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure one external name per league and source maps to exactly one team
    CONSTRAINT unique_alias_per_league_source UNIQUE(external_name, league_id, source)
);

-- Index for fast lookups during match scraping
CREATE INDEX idx_team_aliases_lookup ON team_aliases(external_name, league_id, source);

-- Index for team-based queries
CREATE INDEX idx_team_aliases_team ON team_aliases(team_id);

-- Add updated_at trigger
CREATE TRIGGER update_team_aliases_updated_at
    BEFORE UPDATE ON team_aliases
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add RLS policies
ALTER TABLE team_aliases ENABLE ROW LEVEL SECURITY;

-- Public can read team aliases (needed for match scraping)
CREATE POLICY "Team aliases are viewable by everyone"
    ON team_aliases FOR SELECT
    USING (true);

-- Only admins can insert team aliases
CREATE POLICY "Only admins can insert team aliases"
    ON team_aliases FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

-- Only admins can update team aliases
CREATE POLICY "Only admins can update team aliases"
    ON team_aliases FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

-- Only admins can delete team aliases
CREATE POLICY "Only admins can delete team aliases"
    ON team_aliases FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

COMMENT ON TABLE team_aliases IS 'Maps external team names (from sources like mlssoccer.com) to internal team_ids, contextualized by league. Allows teams with the same external name to map to different internal teams depending on the league.';
COMMENT ON COLUMN team_aliases.external_name IS 'The team name as it appears on the external source (e.g., "IFA" on mlssoccer.com)';
COMMENT ON COLUMN team_aliases.source IS 'The external source where this name is used (e.g., "mlssoccer.com")';
COMMENT ON COLUMN team_aliases.league_id IS 'The league context for this alias. The same external_name can map to different teams in different leagues.';
