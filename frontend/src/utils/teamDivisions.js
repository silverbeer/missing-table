// A team can play one age group in several divisions — Homegrown plus one or
// two Flex conferences (SB-1468). `divisions_by_age_group` holds only one of
// them; `divisions_by_age_group_all` holds every one, home league first.
// Read through these helpers so a lookup never silently drops a division.

/** Every division the team plays this age group in (possibly empty). */
export function teamDivisions(team, ageGroupId) {
  const key = String(ageGroupId);
  const all = team?.divisions_by_age_group_all?.[key];
  if (Array.isArray(all)) return all;
  const single = team?.divisions_by_age_group?.[key];
  return single ? [single] : [];
}

/**
 * The division to show for this age group. Prefers one in `leagueId` (and
 * `divisionId` when given); otherwise the team's primary division.
 * Returns undefined when the team has no division at this age group.
 */
export function teamDivisionFor(
  team,
  ageGroupId,
  { leagueId = null, divisionId = null } = {}
) {
  const divisions = teamDivisions(team, ageGroupId);
  const matches = d =>
    (leagueId == null || Number(d.league_id) === Number(leagueId)) &&
    (divisionId == null || Number(d.id) === Number(divisionId));
  return divisions.find(matches) ?? divisions[0];
}

/** True when the team plays this age group in any division of `leagueId`. */
export function teamPlaysLeague(team, ageGroupId, leagueId) {
  return teamDivisions(team, ageGroupId).some(
    d => Number(d.league_id) === Number(leagueId)
  );
}
