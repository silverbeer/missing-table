-- Season on invitations (SB-287)
--
-- team_player invites that claim a roster spot by jersey number used to
-- resolve the season at REDEMPTION time from today's date - an invite
-- created in June for next season landed in the wrong season. Store the
-- season on the invitation at creation time instead; redemption uses it
-- (with a date-based fallback for legacy NULL rows).

ALTER TABLE invitations
    ADD COLUMN IF NOT EXISTS season_id integer REFERENCES seasons(id);

COMMENT ON COLUMN invitations.season_id IS
    'Season the invite applies to (roster claim scope). Resolved at creation; NULL on legacy rows falls back to current-by-date at redemption.';

-- Backfill pending team_player invites to the current-by-date season.
UPDATE invitations i
SET season_id = s.id
FROM seasons s
WHERE i.season_id IS NULL
  AND i.status = 'pending'
  AND i.invite_type = 'team_player'
  AND s.start_date <= CURRENT_DATE
  AND s.end_date >= CURRENT_DATE;
