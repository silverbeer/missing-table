-- Migration: Add player_id to match_events table
-- Links goal events to specific roster entries for stats tracking
-- player_name column kept for display/backward compatibility

ALTER TABLE match_events
ADD COLUMN player_id INTEGER REFERENCES players(id) ON DELETE SET NULL;

-- Index for lookups (filtering events by player)
CREATE INDEX idx_match_events_player ON match_events(player_id) WHERE player_id IS NOT NULL;

-- Comment
COMMENT ON COLUMN match_events.player_id IS 'Links to roster entry for goal tracking - enables player stats aggregation';
