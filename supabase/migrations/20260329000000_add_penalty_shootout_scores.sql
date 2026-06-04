-- Add penalty shootout score columns to matches table
-- Used when a match ends in a draw after regulation and is decided by penalty kicks.
-- Example: 1-1 (5-4 pens) → home_score=1, away_score=1, home_penalty_score=5, away_penalty_score=4

ALTER TABLE public.matches
    ADD COLUMN IF NOT EXISTS home_penalty_score integer,
    ADD COLUMN IF NOT EXISTS away_penalty_score integer;

-- Constraint: penalty scores must be non-negative when set
ALTER TABLE public.matches
    ADD CONSTRAINT matches_home_penalty_score_non_negative CHECK (home_penalty_score IS NULL OR home_penalty_score >= 0),
    ADD CONSTRAINT matches_away_penalty_score_non_negative CHECK (away_penalty_score IS NULL OR away_penalty_score >= 0);

-- Constraint: both must be set together (can't have one without the other)
ALTER TABLE public.matches
    ADD CONSTRAINT matches_penalty_scores_both_or_neither CHECK (
        (home_penalty_score IS NULL AND away_penalty_score IS NULL)
        OR (home_penalty_score IS NOT NULL AND away_penalty_score IS NOT NULL)
    );

-- Constraint: penalty scores only valid when regulation ended in a draw
ALTER TABLE public.matches
    ADD CONSTRAINT matches_penalty_only_on_draw CHECK (
        home_penalty_score IS NULL
        OR (home_score IS NOT NULL AND away_score IS NOT NULL AND home_score = away_score)
    );
