-- Migration: Add player_id to invitations table
-- Links team_player invitations to a specific roster entry
-- When invite is redeemed, the user account is linked to this roster entry

ALTER TABLE invitations
ADD COLUMN player_id INTEGER REFERENCES players(id) ON DELETE SET NULL;

-- Index for lookups
CREATE INDEX idx_invitations_player ON invitations(player_id) WHERE player_id IS NOT NULL;

-- Comment
COMMENT ON COLUMN invitations.player_id IS 'Links to roster entry (for team_player invites) - user account linked on redemption';
