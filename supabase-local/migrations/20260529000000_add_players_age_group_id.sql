-- Players: per-(team, season) age_group_id (SB-68).
--
-- The 2026-05-28 IFA semifinal surfaced this: team_id=19 (IFA) is
-- age-agnostic, and the roster-fetch endpoint (`/api/teams/{id}/roster`)
-- queried only on (team_id, season_id). So Tom's U14 IFA roster appeared
-- on a U15 match — every age group's roster for an umbrella team lives
-- under the same team_id and there was no column to disambiguate.
--
-- This adds the column. The roster + lineup query path (SB-68) will
-- accept an optional age_group_id filter and apply it strictly when set.
-- Existing rows stay NULL until SB-69 ships a bulk-assign UI so admins
-- can backfill their existing rosters to the right age group. We leave
-- the column nullable for that reason — tightening to NOT NULL is
-- premature.
--
-- Per-season correctness: each `players` row is already per
-- (team_id, season_id). Gabe35's 2025-2026 row gets age_group_id=U14;
-- his 2026-2027 row (created fresh next season) gets U15. No mutation
-- of historical truth needed.

ALTER TABLE public.players
    ADD COLUMN age_group_id integer NULL REFERENCES public.age_groups(id);

-- Index supports the SB-68 strict filter:
-- WHERE team_id = ? AND season_id = ? AND age_group_id = ?
CREATE INDEX idx_players_team_season_age
    ON public.players(team_id, season_id, age_group_id);

COMMENT ON COLUMN public.players.age_group_id IS
    'Per-(team, season) age group this player belongs to. Nullable until '
    'SB-69 ships a backfill UI. Filter by it when querying for a specific '
    'age group''s roster (e.g. live-match lineup).';
