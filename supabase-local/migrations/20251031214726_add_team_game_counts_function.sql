-- Add PostgreSQL function to count games per team
-- This provides optimal performance for the Admin Teams page

-- Function to get game counts for all teams
-- Returns: table of (team_id, game_count) pairs
-- Performance: O(n) single table scan vs O(n²) client-side filtering
CREATE OR REPLACE FUNCTION get_team_game_counts()
RETURNS TABLE (
    team_id INT,
    game_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH home_games AS (
        SELECT home_team_id AS tid, COUNT(*) AS count
        FROM matches
        GROUP BY home_team_id
    ),
    away_games AS (
        SELECT away_team_id AS tid, COUNT(*) AS count
        FROM matches
        GROUP BY away_team_id
    ),
    combined AS (
        SELECT tid, count FROM home_games
        UNION ALL
        SELECT tid, count FROM away_games
    )
    SELECT
        combined.tid::INT AS team_id,
        SUM(combined.count) AS game_count
    FROM combined
    GROUP BY combined.tid;
END;
$$ LANGUAGE plpgsql STABLE;

-- Add comment explaining the optimization
COMMENT ON FUNCTION get_team_game_counts() IS
'Efficiently counts total games (home + away) for all teams.
Used by Admin Teams page to avoid fetching all 100k+ games to the client.
Performance: Scans matches table once and aggregates in database.';
