-- Every string any source might use for a team (SB-822)
--
-- Team identity in MT is the teams.name string and nothing else. There is no
-- alias or previous-name column, and the only normalisation in code is trim +
-- collapse-whitespace. So a feed that spells a team differently does not match,
-- and on the tournament path it does not fail either — it CREATES a second
-- team.
--
-- That has already happened once: 'Intercontinental Football Academy of New
-- England' arrived, matched nothing, and produced a duplicate IFA. It was
-- cleaned up by a one-off fix_duplicate_ifa_teams.py which is not in the repo
-- (fix_*.py is not committed), so the knowledge that the long name means IFA
-- currently exists nowhere in the system. This table is where it goes.
--
-- Three problems, one mechanism, because all three are "given a string from
-- some source, find the team":
--   1. feed variants   — long official name vs the name we display
--   2. renames         — Long Island Soccer Club -> The Island FC West (26/27)
--   3. spelling drift  — across sibling pairs as feeds change

CREATE TABLE IF NOT EXISTS public.team_aliases (
    id         bigserial PRIMARY KEY,
    alias      text NOT NULL,
    team_id    integer NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    -- Does not affect resolution: both kinds resolve identically. It exists so
    -- that later "this club renamed" is distinguishable from "this feed spells
    -- it differently" — different facts about the world.
    kind       text NOT NULL DEFAULT 'feed_variant'
                 CHECK (kind IN ('feed_variant', 'former_name')),
    note       text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Case-insensitive, because every existing name lookup is ilike or case-folded.
-- One alias resolves to exactly one team; two teams claiming the same string is
-- the ambiguity this table exists to remove.
CREATE UNIQUE INDEX IF NOT EXISTS team_aliases_alias_lower_unique
    ON public.team_aliases (lower(alias));

CREATE INDEX IF NOT EXISTS team_aliases_team_idx
    ON public.team_aliases (team_id);

COMMENT ON TABLE public.team_aliases IS
    'Alternate strings that resolve to a team. teams.name is identity and display; this is every other name a feed might use.';

-- Backend reaches this with the service key, which bypasses RLS. Aliases are
-- not secret, but nothing should write them from a client.
ALTER TABLE public.team_aliases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS team_aliases_read ON public.team_aliases;
CREATE POLICY team_aliases_read ON public.team_aliases
    FOR SELECT USING (true);

-- Recover the fact the deleted merge script knew. Guarded on the team existing
-- so the migration is safe on a database where IFA has a different name.
INSERT INTO public.team_aliases (alias, team_id, kind, note)
SELECT 'Intercontinental Football Academy of New England', t.id, 'feed_variant',
       'Official long name in the MLS Next feed; previously created a duplicate team (see SB-822).'
FROM public.teams t
WHERE t.name = 'IFA'
ON CONFLICT DO NOTHING;
