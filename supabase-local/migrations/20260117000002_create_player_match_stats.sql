-- Migration: Create player_match_stats table for per-match statistics
-- Tracks: started, minutes_played, goals (Phase 1)
-- One record per player per match

CREATE TABLE IF NOT EXISTS player_match_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    -- Phase 1 stats
    started BOOLEAN DEFAULT false,
    minutes_played INTEGER DEFAULT 0 CHECK (minutes_played >= 0),
    goals INTEGER DEFAULT 0 CHECK (goals >= 0),

    -- Future stats (reserved, defaults for now)
    assists INTEGER DEFAULT 0 CHECK (assists >= 0),
    yellow_cards INTEGER DEFAULT 0 CHECK (yellow_cards >= 0 AND yellow_cards <= 2),
    red_cards INTEGER DEFAULT 0 CHECK (red_cards >= 0 AND red_cards <= 1),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One stat record per player per match
    UNIQUE(player_id, match_id)
);

-- Indexes for common queries
CREATE INDEX idx_player_match_stats_player ON player_match_stats(player_id);
CREATE INDEX idx_player_match_stats_match ON player_match_stats(match_id);

-- Comments
COMMENT ON TABLE player_match_stats IS 'Per-match statistics for players';
COMMENT ON COLUMN player_match_stats.started IS 'Whether player was in starting lineup';
COMMENT ON COLUMN player_match_stats.minutes_played IS 'Total minutes played in match';
COMMENT ON COLUMN player_match_stats.goals IS 'Goals scored in match';

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_player_match_stats_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER player_match_stats_updated_at_trigger
    BEFORE UPDATE ON player_match_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_player_match_stats_updated_at();

-- RLS Policies
ALTER TABLE player_match_stats ENABLE ROW LEVEL SECURITY;

-- Everyone can view stats (public data)
CREATE POLICY player_match_stats_select_all ON player_match_stats
    FOR SELECT
    USING (true);

-- Service role can do everything
CREATE POLICY player_match_stats_service_all ON player_match_stats
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
