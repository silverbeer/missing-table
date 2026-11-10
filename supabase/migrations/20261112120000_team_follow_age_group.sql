-- SB-1608: a team follow can name one age group of the team (a squad).
--
-- A team row spans several age groups (team_mappings), so a follow keyed by
-- team alone alerts a fan on every age group the club fields. A follow now
-- carries age_group_id:
--
--   age_group_id NULL  -> every age group of the team (what every follow meant
--                         before this migration, so existing follows keep
--                         exactly the alerts they had)
--   age_group_id = N   -> only matches in that age group
--
-- The primary key (user_id, team_id) cannot hold a nullable column, so it
-- becomes a unique constraint that treats NULL as a value: one whole-team row
-- and any number of squad rows per (user, team), never duplicates.
--
-- Expand-only: code that still inserts {user_id, team_id} writes a NULL
-- (whole-team) row and keeps working. The table is in no publication, so it
-- needs no replica identity for deletes. restore_database.py already clears it
-- by user_id (CLEAR_BY_COLUMN), not by id.

ALTER TABLE public.user_team_follows
    ADD COLUMN IF NOT EXISTS age_group_id integer
        REFERENCES public.age_groups(id) ON DELETE CASCADE;

ALTER TABLE public.user_team_follows DROP CONSTRAINT IF EXISTS user_team_follows_pkey;
ALTER TABLE public.user_team_follows DROP CONSTRAINT IF EXISTS user_team_follows_user_team_age_key;
ALTER TABLE public.user_team_follows ADD CONSTRAINT user_team_follows_user_team_age_key
    UNIQUE NULLS NOT DISTINCT (user_id, team_id, age_group_id);

COMMENT ON COLUMN public.user_team_follows.age_group_id IS
    'The squad followed: NULL means every age group of the team (SB-1608).';
COMMENT ON TABLE public.user_team_follows IS
    'Which teams, or squads (team + age group), a user follows for alerts. Cross-club by design. Not channel access.';
