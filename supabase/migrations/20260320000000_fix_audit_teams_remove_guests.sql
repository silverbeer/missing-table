-- Remove guest/tournament/friendly-only teams from audit_teams.
-- These teams appeared in Northeast HG matches but are not division members.
-- The original seed query did not filter by match_type = 'League'.

DELETE FROM public.audit_teams
WHERE season = '2025-2026'
  AND division = 'Northeast'
  AND league = 'Homegrown'
  AND (team, age_group) NOT IN (
    SELECT DISTINCT sub.team, sub.age_group
    FROM (
        SELECT ht.name AS team, ag.name AS age_group
        FROM public.matches  m
        JOIN public.teams       ht ON ht.id = m.home_team_id
        JOIN public.age_groups  ag ON ag.id = m.age_group_id
        JOIN public.divisions    d ON  d.id = m.division_id
        JOIN public.leagues      l ON  l.id = d.league_id
        JOIN public.seasons      s ON  s.id = m.season_id
        JOIN public.match_types mt ON mt.id = m.match_type_id
        WHERE s.name  = '2025-2026'
          AND d.name  = 'Northeast'
          AND l.name  = 'Homegrown'
          AND mt.name = 'League'

        UNION

        SELECT at_.name AS team, ag.name AS age_group
        FROM public.matches  m
        JOIN public.teams       at_ ON at_.id = m.away_team_id
        JOIN public.age_groups   ag ON  ag.id = m.age_group_id
        JOIN public.divisions     d ON   d.id = m.division_id
        JOIN public.leagues       l ON   l.id = d.league_id
        JOIN public.seasons       s ON   s.id = m.season_id
        JOIN public.match_types  mt ON  mt.id = m.match_type_id
        WHERE s.name  = '2025-2026'
          AND d.name  = 'Northeast'
          AND l.name  = 'Homegrown'
          AND mt.name = 'League'
    ) sub
  );
