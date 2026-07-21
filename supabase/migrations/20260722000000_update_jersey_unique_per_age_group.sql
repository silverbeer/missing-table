-- Jersey uniqueness per age group (SB-285)
--
-- Umbrella teams (one teams row fielding U13-U19 via team_mappings, e.g. IFA)
-- could not roster the same jersey number in two age squads in one season:
-- the players unique constraint was (team_id, season_id, jersey_number).
-- Widen it to include age_group_id.
--
-- NULLS NOT DISTINCT (PG15+) preserves the old semantics for rows without an
-- age group: two NULL-age-group rows with the same jersey still conflict.
-- The new constraint is strictly looser than the old one, so no existing
-- rows can conflict and no pre-check is needed.

-- 1. Backfill players.age_group_id where NULL and the team is unambiguous
--    (exactly one team_mappings row). Multi-mapping teams keep NULL until an
--    admin assigns explicitly (SB-69 bulk-assign endpoint).
UPDATE players p
SET age_group_id = tm.age_group_id
FROM (
    SELECT team_id, min(age_group_id) AS age_group_id
    FROM team_mappings
    GROUP BY team_id
    HAVING count(*) = 1
) tm
WHERE p.team_id = tm.team_id
  AND p.age_group_id IS NULL;

-- 2. Replace the unique constraint (idempotent-friendly guards).
ALTER TABLE players
    DROP CONSTRAINT IF EXISTS players_team_id_season_id_jersey_number_key;

ALTER TABLE players
    DROP CONSTRAINT IF EXISTS players_team_season_ag_jersey_key;

ALTER TABLE players
    ADD CONSTRAINT players_team_season_ag_jersey_key
    UNIQUE NULLS NOT DISTINCT (team_id, season_id, age_group_id, jersey_number);

COMMENT ON CONSTRAINT players_team_season_ag_jersey_key ON players IS
    'Jersey numbers are unique per (team, season, age group). NULLS NOT DISTINCT: rows without an age group behave as one squad.';
