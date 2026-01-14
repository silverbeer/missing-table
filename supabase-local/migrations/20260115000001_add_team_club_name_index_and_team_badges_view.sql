-- Purpose: Speed up club/team listings with an index and a lightweight badges view

CREATE INDEX IF NOT EXISTS idx_teams_club_name ON teams(club_id, name);

CREATE OR REPLACE VIEW teams_with_league_badges AS
SELECT
    t.id,
    t.name,
    t.club_id,
    t.league_id,
    l.name AS league_name,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT dl.name), NULL) AS mapping_league_names
FROM teams t
LEFT JOIN leagues l ON l.id = t.league_id
LEFT JOIN team_mappings tm ON tm.team_id = t.id
LEFT JOIN divisions d ON d.id = tm.division_id
LEFT JOIN leagues dl ON dl.id = d.league_id
GROUP BY t.id, t.name, t.club_id, t.league_id, l.name;
