-- Jersey uniqueness applies to active players only (SB-809)
--
-- Deleting a roster player is a soft delete (players.is_active = false); the
-- row stays so match_events keep their attribution and player_match_stats
-- survive (that FK is ON DELETE CASCADE). But the unique constraint from
-- SB-285 counted those tombstones, so a deleted player's jersey number was
-- burned for the rest of the season -- re-adding it failed at the DB.
--
-- Scope uniqueness to is_active rows. Soft-deleted rows may now share a
-- number with the active player wearing it, and with each other.
--
-- The new index is strictly looser than the constraint it replaces (same key
-- columns, same NULLS NOT DISTINCT semantics, plus a WHERE clause), so no
-- existing row can conflict and no pre-check is needed.

ALTER TABLE players
    DROP CONSTRAINT IF EXISTS players_team_season_ag_jersey_key;

DROP INDEX IF EXISTS players_active_team_season_ag_jersey_key;

CREATE UNIQUE INDEX players_active_team_season_ag_jersey_key
    ON players (team_id, season_id, age_group_id, jersey_number)
    NULLS NOT DISTINCT
    WHERE is_active;

COMMENT ON INDEX players_active_team_season_ag_jersey_key IS
    'Jersey numbers are unique per (team, season, age group) among active players. Soft-deleted rows (is_active = false) are excluded so a deleted player''s number can be reissued. NULLS NOT DISTINCT: rows without an age group behave as one squad.';
