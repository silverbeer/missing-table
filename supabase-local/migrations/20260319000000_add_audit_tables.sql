-- Add audit tables for Northeast HG division data-integrity auditing.
-- Two tables:
--   audit_teams  — team registry and audit scheduling state (one row per team × age-group)
--   audit_events — one row per audit run that found discrepancies

-- ─── audit_teams ────────────────────────────────────────────────────────────

CREATE TABLE public.audit_teams (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    team             text        NOT NULL,
    age_group        text        NOT NULL,
    league           text        NOT NULL,
    division         text        NOT NULL,
    season           text        NOT NULL,
    last_audited_at  timestamptz,                  -- null = never audited (highest priority)
    last_audit_status text        CHECK (last_audit_status IN ('clean', 'findings', 'error')),
    findings_count   int         NOT NULL DEFAULT 0,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (team, age_group, league, division, season)
);

COMMENT ON TABLE public.audit_teams IS
    'One row per team × age-group scheduled for weekly data-integrity auditing.';

COMMENT ON COLUMN public.audit_teams.last_audited_at IS
    'UTC timestamp of the most recent completed audit for this row. NULL = never audited.';

-- ─── audit_events ────────────────────────────────────────────────────────────

CREATE TABLE public.audit_events (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id      text        UNIQUE NOT NULL,      -- MSA-generated hex ID per audit run
    audit_run_id  text        NOT NULL,             -- same as event_id (kept for future correlation)
    team          text        NOT NULL,
    age_group     text        NOT NULL,
    league        text        NOT NULL,
    division      text        NOT NULL,
    season        text        NOT NULL,
    findings      jsonb       NOT NULL DEFAULT '[]', -- list of AuditFinding dicts
    status        text        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'processed', 'ignored')),
    processed_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.audit_events IS
    'One row per audit run that produced findings. Clean runs (0 findings) are not stored here.';

COMMENT ON COLUMN public.audit_events.findings IS
    'JSON array of AuditFinding objects — each describes a single discrepancy found.';

-- ─── RLS — service key bypasses; no user-facing access needed ────────────────

ALTER TABLE public.audit_teams  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

-- ─── Indexes ─────────────────────────────────────────────────────────────────

-- Scheduling query: find least-recently-audited team in a season/division/league
CREATE INDEX idx_audit_teams_schedule
    ON public.audit_teams (season, division, league, last_audited_at NULLS FIRST);

-- Processor query: pending events by season
CREATE INDEX idx_audit_events_pending
    ON public.audit_events (status, season)
    WHERE status = 'pending';

-- Fast event lookup for PATCH
CREATE INDEX idx_audit_events_event_id
    ON public.audit_events (event_id);

-- ─── Seed audit_teams from existing Northeast HG match data ──────────────────
-- Derives the team list automatically from matches already in the DB.
-- Covers both home and away teams for U13/U14/U15/U16, Homegrown, Northeast.

INSERT INTO public.audit_teams (team, age_group, league, division, season)
SELECT DISTINCT
    ht.name     AS team,
    ag.name     AS age_group,
    l.name      AS league,
    d.name      AS division,
    s.name      AS season
FROM public.matches  m
JOIN public.teams      ht ON ht.id = m.home_team_id
JOIN public.age_groups ag ON ag.id = m.age_group_id
JOIN public.divisions   d ON  d.id = m.division_id
JOIN public.leagues     l ON  l.id = d.league_id
JOIN public.seasons     s ON  s.id = m.season_id
WHERE s.name    = '2025-2026'
  AND d.name    = 'Northeast'
  AND l.name    = 'Homegrown'
  AND ag.name  IN ('U13', 'U14', 'U15', 'U16')

UNION

SELECT DISTINCT
    at_.name    AS team,
    ag.name     AS age_group,
    l.name      AS league,
    d.name      AS division,
    s.name      AS season
FROM public.matches  m
JOIN public.teams      at_ ON at_.id = m.away_team_id
JOIN public.age_groups  ag ON  ag.id = m.age_group_id
JOIN public.divisions    d ON   d.id = m.division_id
JOIN public.leagues      l ON   l.id = d.league_id
JOIN public.seasons      s ON   s.id = m.season_id
WHERE s.name    = '2025-2026'
  AND d.name    = 'Northeast'
  AND l.name    = 'Homegrown'
  AND ag.name  IN ('U13', 'U14', 'U15', 'U16')

ON CONFLICT (team, age_group, league, division, season) DO NOTHING;
