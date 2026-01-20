-- Migration: Add jersey_number to invitations table
-- Allows creating team_player invites with a jersey number
-- When invite is redeemed, a player roster entry is created with this number

ALTER TABLE invitations
ADD COLUMN jersey_number INTEGER CHECK (jersey_number IS NULL OR (jersey_number >= 1 AND jersey_number <= 99));

-- Comment
COMMENT ON COLUMN invitations.jersey_number IS 'Jersey number for team_player invites - creates roster entry on redemption';
