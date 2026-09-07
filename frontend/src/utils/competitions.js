/**
 * Competition and league-hierarchy helpers shared by the Table and Matches
 * tabs (SB-1039, SB-1040).
 *
 * MLS NEXT is organised Division (Homegrown, Academy) → Competition (League,
 * Flex) → Conference. In MT a competition's conferences can live under a
 * child league row — Flex is a league whose `parent_league_id` is Homegrown
 * and whose `match_type_id` is Flex — so anything that groups by "league"
 * has to resolve a child to its parent first. These are pure so both tabs
 * read the same rule and a spec can pin it directly.
 */

/** "League + Flex": the combined view labelled by what it combines. */
export const combinedLabel = names => (names || []).filter(Boolean).join(' + ');

/** Title for the combined chip: honest about being a record, not a standing. */
export const combinedTitle = names => {
  const label = combinedLabel(names);
  if (!label) return '';
  return (
    `Combined record across ${label} — the competitions that ` +
    'qualify for MLS NEXT Cup. A record, not a standing.'
  );
};

/**
 * The top-level division a league belongs to: the league itself when it has
 * no parent, its parent otherwise. Unknown ids come back as null. A league
 * row without the column (an API that predates it) is its own top level.
 */
export const topLevelLeague = (leagues, leagueId) => {
  if (leagueId === null || leagueId === undefined) return null;
  const byId = new Map((leagues || []).map(l => [Number(l.id), l]));
  let league = byId.get(Number(leagueId)) || null;
  // Bounded walk: a cycle in the data must not hang the page.
  for (let hops = 0; league?.parent_league_id && hops < 5; hops++) {
    const parent = byId.get(Number(league.parent_league_id));
    if (!parent) break;
    league = parent;
  }
  return league;
};

/**
 * The top-level division name for a match, from its conference's league.
 * Falls back to the league name the match carries when the league list does
 * not know the id — older fixtures, or a list that has not loaded yet.
 */
export const topLevelLeagueName = (leagues, match) => {
  const division = match?.division || null;
  const leagueId = division?.league_id ?? division?.leagues?.id ?? null;
  const resolved = topLevelLeague(leagues, leagueId);
  if (resolved) return resolved.name;
  return division?.leagues?.name ?? null;
};

/**
 * The competition whose tables a league's conferences are — "League" for
 * Homegrown and Academy, "Flex" for the Flex league — or null when the
 * league does not say (an API that predates `match_type_id`).
 */
export const competitionOfLeague = (leagues, matchTypes, leagueId) => {
  const league = (leagues || []).find(l => Number(l.id) === Number(leagueId));
  const typeId = league?.match_type_id;
  if (typeId === null || typeId === undefined) return null;
  const type = (matchTypes || []).find(t => Number(t.id) === Number(typeId));
  return type?.name ?? null;
};
