/**
 * Who may edit a given match.
 *
 * The rule itself is old — admin edits anything, a club manager edits any
 * match involving a team in their club, a team manager edits their own team's
 * matches — but it had been copy-pasted per screen. The copies drifted:
 * `MatchDetailView` granted *every* club manager, without checking the club.
 * Tournament rows needed the same rule again (SB-906), so it lives here once.
 *
 * Match shapes differ by endpoint. The league list carries flat
 * `home_team_id` / `away_team_id`; tournament rows carry nested
 * `home_team: { id }` and `home_team_club: { id }`. Both are read here so
 * callers don't have to normalise first.
 */

/** Team ids on both sides, from either match shape. */
export function matchTeamIds(match) {
  if (!match) return { homeTeamId: null, awayTeamId: null };
  return {
    homeTeamId: match.home_team_id ?? match.home_team?.id ?? null,
    awayTeamId: match.away_team_id ?? match.away_team?.id ?? null,
  };
}

/**
 * Club ids on both sides. Tournament matches embed the club; league matches
 * don't, so a caller with a teams list passes `resolveClubId` to look one up.
 */
export function matchClubIds(match, resolveClubId = null) {
  if (!match) return { homeClubId: null, awayClubId: null };
  const { homeTeamId, awayTeamId } = matchTeamIds(match);
  const lookup =
    typeof resolveClubId === 'function' ? resolveClubId : () => null;
  return {
    homeClubId: match.home_team_club?.id ?? lookup(homeTeamId) ?? null,
    awayClubId: match.away_team_club?.id ?? lookup(awayTeamId) ?? null,
  };
}

/**
 * @param {object} match
 * @param {object} viewer  { isAdmin, isClubManager, isTeamManager, clubId, teamId }
 * @param {object} [options]
 * @param {(teamId:number)=>number|null} [options.resolveClubId]
 * @returns {boolean}
 */
export function canEditMatch(match, viewer, { resolveClubId = null } = {}) {
  if (!match || !viewer) return false;
  if (viewer.isAdmin) return true;

  const { homeTeamId, awayTeamId } = matchTeamIds(match);

  if (viewer.isClubManager && viewer.clubId != null) {
    const { homeClubId, awayClubId } = matchClubIds(match, resolveClubId);
    if (homeClubId === viewer.clubId || awayClubId === viewer.clubId)
      return true;
  }

  if (viewer.isTeamManager && viewer.teamId != null) {
    if (homeTeamId === viewer.teamId || awayTeamId === viewer.teamId)
      return true;
  }

  return false;
}
