/**
 * Role comparison helpers.
 *
 * `user_profiles_role_check` accepts both spellings of every non-admin role —
 * `club-fan` and `club_fan`, `team-manager` and `team_manager`, and so on — and
 * invites have created real users under each. An exact-match role list
 * therefore admits only half of its intended audience, silently, with no error
 * anywhere (SB-668).
 *
 * Compare normalized forms instead, so a list can be written in one spelling
 * and still mean what it says.
 */

/** Canonical form of a role: hyphens, not underscores. */
export function normalizeRole(role) {
  return (role || '').replace(/_/g, '-');
}

/** True when `role` matches any entry of `required`, ignoring spelling. */
export function hasAnyRole(required, role) {
  if (!Array.isArray(required) || !required.length) return false;
  const actual = normalizeRole(role);
  if (!actual) return false;
  return required.some(r => normalizeRole(r) === actual);
}

/**
 * Who may see the team page — roster, Golden Boot board and all.
 *
 * Defined once because it is checked twice: App.vue decides whether the My Club
 * tab appears, and TeamRosterRouter decides whether the page renders. Those two
 * lists drifted apart the first time (SB-668), so the tab appeared and the page
 * behind it said "Players Only".
 *
 * Written in one spelling; hasAnyRole normalizes the other.
 */
export const TEAM_PAGE_ROLES = [
  'admin',
  'club_manager',
  'club-fan',
  'team-manager',
  'team-player',
  'team-fan',
];

/**
 * Who may start live scoring a match. Kept in step with the Add Match tab and
 * with useLiveMatch's canManage, which gates the clock controls themselves.
 */
export const LIVE_SCORER_ROLES = ['admin', 'club_manager', 'team-manager'];

/**
 * Query string for the LIVE tab's `/api/matches/live` poll.
 *
 * SB-910 narrowed that endpoint to matches with a running live-scoring clock.
 * But the clock is started from the live view, and the LIVE tab is the web's
 * only way into it — so a match merely marked in progress could never be
 * live-scored from the web (SB-1532). Scorers get every match under way, so
 * they can reach Start Match; everyone else keeps the narrowed list, where the
 * tab promises a feed someone is driving.
 */
export function liveMatchesQuery(role) {
  return hasAnyRole(LIVE_SCORER_ROLES, role) ? '?include_manual=true' : '';
}
