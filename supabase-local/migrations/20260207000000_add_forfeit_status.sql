-- Add 'forfeit' to match_status enum
ALTER TYPE public.match_status ADD VALUE IF NOT EXISTS 'forfeit';

-- Add forfeit_team_id column to matches table
ALTER TABLE public.matches
  ADD COLUMN IF NOT EXISTS forfeit_team_id integer REFERENCES public.teams(id);
