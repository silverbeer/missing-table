-- Add CHECK constraint: forfeit_team_id must be NULL when status != forfeit,
-- and must be one of (home_team_id, away_team_id) when status = forfeit
-- (Separate migration because PostgreSQL can't use a new enum value in the same transaction it was added)
ALTER TABLE public.matches
  ADD CONSTRAINT chk_forfeit_team_consistency
    CHECK (
      (match_status != 'forfeit' AND forfeit_team_id IS NULL)
      OR
      (match_status = 'forfeit' AND forfeit_team_id IS NOT NULL
       AND forfeit_team_id IN (home_team_id, away_team_id))
    );
