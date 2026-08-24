-- Every string any source might use for a team (SB-822)
--
-- A team_aliases table already existed in production but in NO migration and
-- not in the baseline schema — it was created out of band. Shape:
--
--   id, team_id, league_id, external_name,
--   source varchar DEFAULT 'mlssoccer.com', created_at, updated_at
--   UNIQUE (external_name, league_id, source)
--
-- Empty, referenced by no code. Built for this exact problem in the
-- mlssoccer.com scraper era and never populated.
--
-- This migration adopts that table rather than replacing it, brings it into
-- version control so fresh databases match production, and adds what it was
-- missing. `source` is genuinely useful now that MLS Next has moved to Kitman:
-- the same team can carry one string from mlssoccer.com and another from
-- kitman, and this distinguishes them.
--
-- Why this table matters: team identity is the teams.name string, so a feed
-- spelling a team differently does not match — and on the tournament path it
-- does not fail either, it CREATES a second team. That is how
-- 'Intercontinental Football Academy of New England' became a duplicate IFA,
-- merged back by a fix_duplicate_ifa_teams.py that is no longer in the repo.

-- Matches the shape already in production, so a fresh database lands in the
-- same place a drifted one is already in.
CREATE TABLE IF NOT EXISTS public.team_aliases (
    id            serial PRIMARY KEY,
    team_id       integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    league_id     integer REFERENCES public.leagues(id) ON DELETE CASCADE,
    external_name character varying NOT NULL,
    source        character varying NOT NULL DEFAULT 'mlssoccer.com',
    created_at    timestamptz DEFAULT now(),
    updated_at    timestamptz DEFAULT now()
);

-- A former name is a property of the club, not of a league, so league_id has
-- to be optional. It was NOT NULL, which would have forced an arbitrary league
-- onto 'Long Island Soccer Club'.
ALTER TABLE public.team_aliases ALTER COLUMN league_id DROP NOT NULL;

-- Distinguishes "this club renamed" from "this feed spells it differently".
-- Does NOT affect resolution — both kinds resolve identically — but a year
-- from now they are different facts about the world.
ALTER TABLE public.team_aliases
    ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'feed_variant';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.team_aliases'::regclass AND conname = 'team_aliases_kind_check'
    ) THEN
        ALTER TABLE public.team_aliases
            ADD CONSTRAINT team_aliases_kind_check CHECK (kind IN ('feed_variant', 'former_name'));
    END IF;
END $$;

-- The existing UNIQUE (external_name, league_id, source) stops colliding once
-- league_id can be NULL: in Postgres, NULLs are distinct by default, so two
-- former-name rows for the same string would both be accepted. NULLS NOT
-- DISTINCT (PG15+; this is PG17) makes the constraint mean what it says.
DROP INDEX IF EXISTS public.unique_alias_per_league_source_nulls;
CREATE UNIQUE INDEX IF NOT EXISTS unique_alias_per_league_source_nulls
    ON public.team_aliases (lower(external_name), league_id, source) NULLS NOT DISTINCT;

CREATE INDEX IF NOT EXISTS team_aliases_team_idx ON public.team_aliases (team_id);
CREATE INDEX IF NOT EXISTS team_aliases_name_idx ON public.team_aliases (lower(external_name));

COMMENT ON TABLE public.team_aliases IS
    'Alternate strings that resolve to a team. teams.name is identity and display; this is every other name a source uses for it.';
COMMENT ON COLUMN public.team_aliases.source IS
    'Which external system uses this name (e.g. mlssoccer.com, kitman). The same team may be spelled differently per feed.';
COMMENT ON COLUMN public.team_aliases.kind IS
    'feed_variant = another current spelling; former_name = the club used to be called this.';

ALTER TABLE public.team_aliases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS team_aliases_read ON public.team_aliases;
CREATE POLICY team_aliases_read ON public.team_aliases FOR SELECT USING (true);

-- Recover the fact the deleted merge script knew. league_id NULL: the long
-- name is the club's official name, not a per-league spelling.
INSERT INTO public.team_aliases (external_name, team_id, league_id, source, kind)
SELECT 'Intercontinental Football Academy of New England', t.id, NULL, 'mlssoccer.com', 'feed_variant'
FROM public.teams t
WHERE t.name = 'IFA'
ON CONFLICT DO NOTHING;
