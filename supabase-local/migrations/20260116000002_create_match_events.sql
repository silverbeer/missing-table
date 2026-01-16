-- Migration: Create match_events table for live match activity stream
-- Stores goals, chat messages, and status changes during live matches

CREATE TABLE IF NOT EXISTS match_events (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('goal', 'message', 'status_change')),

    -- Goal-specific fields
    team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    player_name VARCHAR(200),

    -- Message content (required for all event types)
    message TEXT NOT NULL,

    -- User who created the event
    created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    created_by_username VARCHAR(100),

    -- Soft delete for moderation
    is_deleted BOOLEAN DEFAULT false,
    deleted_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    deleted_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Auto-expiry for messages (set by trigger, NULL for goals/status_change)
    expires_at TIMESTAMPTZ
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_match_events_match_id ON match_events(match_id);
CREATE INDEX IF NOT EXISTS idx_match_events_created_at ON match_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_events_type ON match_events(event_type);
CREATE INDEX IF NOT EXISTS idx_match_events_expires ON match_events(expires_at)
    WHERE expires_at IS NOT NULL AND is_deleted = false;

-- Comments
COMMENT ON TABLE match_events IS 'Activity stream for live matches: goals, chat messages, status changes';
COMMENT ON COLUMN match_events.event_type IS 'Type of event: goal, message, or status_change';
COMMENT ON COLUMN match_events.expires_at IS 'Auto-set to 10 days from created_at for messages (cleanup target)';

-- Trigger function to auto-set expires_at for messages
CREATE OR REPLACE FUNCTION set_match_event_message_expiry()
RETURNS TRIGGER AS $$
BEGIN
    -- Only set expiry for message events (goals and status_change are permanent)
    IF NEW.event_type = 'message' THEN
        NEW.expires_at := NEW.created_at + INTERVAL '10 days';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Create trigger
DROP TRIGGER IF EXISTS match_event_set_expiry ON match_events;
CREATE TRIGGER match_event_set_expiry
    BEFORE INSERT ON match_events
    FOR EACH ROW
    EXECUTE FUNCTION set_match_event_message_expiry();

-- RLS Policies
ALTER TABLE match_events ENABLE ROW LEVEL SECURITY;

-- Everyone can read non-deleted events
CREATE POLICY match_events_select_policy ON match_events
    FOR SELECT
    USING (is_deleted = false);

-- Authenticated users can insert events
CREATE POLICY match_events_insert_policy ON match_events
    FOR INSERT
    WITH CHECK (true);

-- Admins and managers can update (for soft delete)
CREATE POLICY match_events_update_policy ON match_events
    FOR UPDATE
    USING (true);
