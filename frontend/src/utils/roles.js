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
