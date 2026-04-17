-- Quality of Play rankings scraped weekly from MLS Next standings page
CREATE TABLE qop_rankings (
    id SERIAL PRIMARY KEY,
    week_of DATE NOT NULL,
    division_id INTEGER NOT NULL REFERENCES divisions(id),
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id),
    rank INTEGER NOT NULL CHECK (rank >= 1),
    team_name TEXT NOT NULL,
    team_id INTEGER REFERENCES teams(id),
    matches_played INTEGER,
    att_score NUMERIC(5,1),
    def_score NUMERIC(5,1),
    qop_score NUMERIC(5,1) NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (week_of, division_id, age_group_id, rank)
);

CREATE INDEX idx_qop_rankings_lookup
    ON qop_rankings (division_id, age_group_id, week_of DESC);

ALTER TABLE qop_rankings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "qop_rankings_select" ON qop_rankings
    FOR SELECT USING (true);
