/**
 * Role matching (SB-668).
 *
 * user_profiles_role_check accepts both spellings of every non-admin role, and
 * invites have created real users under each. An exact-match role list admits
 * only half its intended audience — silently, with no error anywhere — which is
 * the bug these pin.
 */

import { describe, it, expect } from 'vitest';
import { normalizeRole, hasAnyRole } from '@/utils/roles';

// Exactly the set user_profiles_role_check permits.
const DB_ROLES = [
  'admin',
  'club_manager',
  'club-fan',
  'club_fan',
  'team-manager',
  'team_manager',
  'team-player',
  'team_player',
  'team-fan',
  'team_fan',
];

// What App.vue lists for the My Club tab, written in one spelling.
const MY_CLUB = [
  'admin',
  'club_manager',
  'club-fan',
  'team-manager',
  'team-player',
  'team-fan',
];

describe('normalizeRole', () => {
  it('collapses both spellings to one form', () => {
    expect(normalizeRole('team_manager')).toBe('team-manager');
    expect(normalizeRole('team-manager')).toBe('team-manager');
    expect(normalizeRole('club_fan')).toBe('club-fan');
  });

  it('is safe on empty input', () => {
    expect(normalizeRole(null)).toBe('');
    expect(normalizeRole(undefined)).toBe('');
    expect(normalizeRole('')).toBe('');
  });
});

describe('hasAnyRole', () => {
  it('matches regardless of which spelling each side uses', () => {
    expect(hasAnyRole(['team-manager'], 'team_manager')).toBe(true);
    expect(hasAnyRole(['team_manager'], 'team-manager')).toBe(true);
    expect(hasAnyRole(['club_manager'], 'club_manager')).toBe(true);
  });

  it('admits every role the My Club tab is meant to admit', () => {
    // Both spellings of each, since either can exist in the database.
    const admitted = DB_ROLES.filter(r => hasAnyRole(MY_CLUB, r));
    expect(admitted).toEqual(DB_ROLES);
  });

  it('still excludes a role that is not listed', () => {
    expect(hasAnyRole(['admin', 'club_manager'], 'team-fan')).toBe(false);
    expect(hasAnyRole(['admin', 'club_manager'], 'team_fan')).toBe(false);
  });

  it('denies when there is no role or no list', () => {
    expect(hasAnyRole(MY_CLUB, null)).toBe(false);
    expect(hasAnyRole(MY_CLUB, '')).toBe(false);
    expect(hasAnyRole([], 'admin')).toBe(false);
    expect(hasAnyRole(undefined, 'admin')).toBe(false);
  });

  it('does not treat a partial name as a match', () => {
    expect(hasAnyRole(['team-manager'], 'team')).toBe(false);
    expect(hasAnyRole(['club-fan'], 'fan')).toBe(false);
  });
});
