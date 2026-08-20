/**
 * Auth store role comparisons accept either spelling (SB-798).
 *
 * user_profiles_role_check permits both forms of most roles — club-fan and
 * club_fan, team-manager and team_manager — and real accounts exist under each,
 * because one signup path wrote the underscore form while the others wrote the
 * hyphen form. Exact-string comparisons therefore covered only half of their
 * audience, silently: no error, just a capability quietly missing.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('@/config/supabase', () => ({
  supabase: { auth: { onAuthStateChange: vi.fn() } },
  getOAuthRedirectUrl: () => 'http://test',
}));
vi.mock('@/config/api', () => ({ getApiBaseUrl: () => 'http://test' }));

import { useAuthStore } from '@/stores/auth';

const store = useAuthStore();

const asRole = role => {
  store.state.profile = { role, team_id: null, club_id: null };
};

beforeEach(() => {
  asRole(null);
});

describe('auth store role spelling (SB-798)', () => {
  it.each(['club-fan', 'club_fan'])('treats %s as a club fan', role => {
    // 10 accounts are club-fan and 2 are club_fan. Before this, the
    // underscore-only check recognised the 2 and missed the 10.
    asRole(role);
    expect(store.isClubFan.value).toBe(true);
  });

  it.each(['team-manager', 'team_manager'])(
    'treats %s as a team manager',
    role => {
      asRole(role);
      expect(store.isTeamManager.value).toBe(true);
    }
  );

  it.each(['team-player', 'team_player'])('treats %s as a player', role => {
    asRole(role);
    expect(store.isPlayer.value).toBe(true);
  });

  it.each(['team-player', 'team_player'])(
    'lets %s browse all leagues',
    role => {
      // canBrowseAll is built on isPlayer and is consumed by MatchesView, so
      // the underscore form would have silently lost league browsing.
      asRole(role);
      expect(store.canBrowseAll.value).toBe(true);
    }
  );

  it('recognises club_manager, whose canonical form is the underscore one', () => {
    // Deliberately asymmetric: 'club-manager' is not permitted by the role
    // constraint at all, so this is one spelling rather than two.
    asRole('club_manager');
    expect(store.isClubManager.value).toBe(true);
  });

  it('does not confuse one role for another', () => {
    asRole('team-fan');
    expect(store.isPlayer.value).toBe(false);
    expect(store.isTeamManager.value).toBe(false);
    expect(store.isClubFan.value).toBe(false);
    expect(store.isAdmin.value).toBe(false);
  });

  it('treats an absent role as no privileges', () => {
    asRole(undefined);
    expect(store.isAdmin.value).toBe(false);
    expect(store.isClubManager.value).toBe(false);
    expect(store.canBrowseAll.value).toBe(false);
  });

  it('keeps admin a single exact role', () => {
    asRole('admin');
    expect(store.isAdmin.value).toBe(true);
    asRole('Admin');
    // Case is not a spelling variant the constraint permits; do not invent one.
    expect(store.isAdmin.value).toBe(false);
  });
});
