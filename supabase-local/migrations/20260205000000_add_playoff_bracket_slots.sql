-- Playoff Bracket Slots table
-- Stores the structure of an 8-team single elimination bracket:
-- 4 Quarterfinals -> 2 Semifinals -> 1 Final
-- Each bracket is scoped to (league_id, season_id, age_group_id).
-- Self-referencing FKs (home_source_slot_id, away_source_slot_id) link
-- later rounds to their feeder slots for automatic advancement.

CREATE TABLE public.playoff_bracket_slots (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES public.leagues(id),
    season_id INTEGER NOT NULL REFERENCES public.seasons(id),
    age_group_id INTEGER NOT NULL REFERENCES public.age_groups(id),
    round VARCHAR(20) NOT NULL CHECK (round IN ('quarterfinal', 'semifinal', 'final')),
    bracket_position INTEGER NOT NULL,
    match_id INTEGER REFERENCES public.matches(id) ON DELETE SET NULL,
    home_seed INTEGER,
    away_seed INTEGER,
    home_source_slot_id INTEGER REFERENCES public.playoff_bracket_slots(id),
    away_source_slot_id INTEGER REFERENCES public.playoff_bracket_slots(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(league_id, season_id, age_group_id, round, bracket_position)
);

CREATE INDEX idx_playoff_bracket_league_season_ag
    ON public.playoff_bracket_slots(league_id, season_id, age_group_id);

-- RLS: visible to all authenticated users, writable by admins only
ALTER TABLE public.playoff_bracket_slots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "playoff_bracket_slots_select"
    ON public.playoff_bracket_slots FOR SELECT USING (true);

CREATE POLICY "playoff_bracket_slots_admin_insert"
    ON public.playoff_bracket_slots FOR INSERT WITH CHECK (public.is_admin());

CREATE POLICY "playoff_bracket_slots_admin_update"
    ON public.playoff_bracket_slots FOR UPDATE USING (public.is_admin());

CREATE POLICY "playoff_bracket_slots_admin_delete"
    ON public.playoff_bracket_slots FOR DELETE USING (public.is_admin());
