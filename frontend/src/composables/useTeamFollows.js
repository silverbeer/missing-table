/**
 * Team-follows composable (SB-55).
 *
 * Singleton reactive state shared by every FollowButton instance and the
 * NotificationsCard "Teams you follow" list. Mirrors the useAuthStore
 * pattern: module-level reactive state, useTeamFollows() returns the
 * same refs every call.
 *
 * Backend endpoints (all idempotent):
 *   GET    /api/users/me/team-follows           → { follows: [{ team_id, age_group_id, team, age_group, ... }] }
 *   POST   /api/users/me/team-follows           → 201; body { team_id, age_group_id? }
 *   DELETE /api/users/me/team-follows/{id}[?age_group_id=N] → 204
 *
 * A follow is for match alerts. `age_group_id` null follows every age group
 * of the team; a value follows that squad only (SB-1608, SB-1618).
 */

import { reactive, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

const state = reactive({
  followedTeamIds: new Set(),
  follows: [],
  loaded: false,
  loading: false,
  error: null,
});

let inflightLoad = null;

async function fetchFollows() {
  const authStore = useAuthStore();
  if (!authStore.isAuthenticated.value) {
    state.followedTeamIds = new Set();
    state.follows = [];
    state.loaded = true;
    return;
  }

  state.loading = true;
  state.error = null;
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/users/me/team-follows`
    );
    const rows = data?.follows || [];
    state.follows = rows;
    state.followedTeamIds = new Set(rows.map(r => r.team_id));
    state.loaded = true;
  } catch (err) {
    state.error = err.message || String(err);
    state.followedTeamIds = new Set();
    state.follows = [];
  } finally {
    state.loading = false;
  }
}

export function useTeamFollows() {
  const authStore = useAuthStore();

  const ensureLoaded = () => {
    if (state.loaded || state.loading) return inflightLoad || Promise.resolve();
    inflightLoad = fetchFollows().finally(() => {
      inflightLoad = null;
    });
    return inflightLoad;
  };

  const refresh = () => {
    inflightLoad = fetchFollows().finally(() => {
      inflightLoad = null;
    });
    return inflightLoad;
  };

  const rowsFor = teamId =>
    state.follows.filter(r => Number(r.team_id) === Number(teamId));

  // With an age group: following that squad, directly or through a
  // whole-team follow. Without: following any part of the team.
  const isFollowing = (teamId, ageGroupId = null) => {
    const rows = rowsFor(teamId);
    if (ageGroupId == null) return rows.length > 0;
    return rows.some(
      r =>
        r.age_group_id == null || Number(r.age_group_id) === Number(ageGroupId)
    );
  };

  // True when the squad is covered only by a whole-team follow.
  const followsWholeTeam = teamId =>
    rowsFor(teamId).some(r => r.age_group_id == null);

  const follow = async (teamId, ageGroupId = null) => {
    const id = Number(teamId);
    if (isFollowing(id, ageGroupId)) return { success: true };

    const age = ageGroupId == null ? null : Number(ageGroupId);
    const before = state.follows;
    state.follows = [...before, { team_id: id, age_group_id: age }];
    state.followedTeamIds = new Set([...state.followedTeamIds, id]);
    state.error = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/team-follows`,
        {
          method: 'POST',
          body: JSON.stringify(
            age == null ? { team_id: id } : { team_id: id, age_group_id: age }
          ),
        }
      );
      refresh();
      return { success: true };
    } catch (err) {
      state.follows = before;
      state.followedTeamIds = new Set(before.map(r => r.team_id));
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  // With an age group, stop that squad only; if it is covered by a whole-team
  // follow, that follow goes (it cannot be narrowed without knowing every
  // age group the team plays). Without, stop every follow of the team.
  const unfollow = async (teamId, ageGroupId = null) => {
    const id = Number(teamId);
    if (!isFollowing(id, ageGroupId)) return { success: true };

    const squadOnly = ageGroupId != null && !followsWholeTeam(id);
    const removed = state.follows.filter(
      r =>
        Number(r.team_id) === id &&
        (!squadOnly || Number(r.age_group_id) === Number(ageGroupId))
    );
    const before = state.follows;
    state.follows = before.filter(r => !removed.includes(r));
    state.followedTeamIds = new Set(state.follows.map(r => r.team_id));
    state.error = null;
    const query = squadOnly ? `?age_group_id=${Number(ageGroupId)}` : '';
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/team-follows/${id}${query}`,
        { method: 'DELETE' }
      );
      refresh();
      return { success: true };
    } catch (err) {
      state.follows = before;
      state.followedTeamIds = new Set(before.map(r => r.team_id));
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  const toggle = async (teamId, ageGroupId = null) => {
    return isFollowing(teamId, ageGroupId)
      ? unfollow(teamId, ageGroupId)
      : follow(teamId, ageGroupId);
  };

  return {
    follows: computed(() => state.follows),
    followedTeamIds: computed(() => state.followedTeamIds),
    loaded: computed(() => state.loaded),
    loading: computed(() => state.loading),
    error: computed(() => state.error),
    ensureLoaded,
    refresh,
    isFollowing,
    followsWholeTeam,
    follow,
    unfollow,
    toggle,
  };
}

// Test-only: reset module-level singleton between tests.
export function _resetTeamFollowsForTest() {
  state.followedTeamIds = new Set();
  state.follows = [];
  state.loaded = false;
  state.loading = false;
  state.error = null;
  inflightLoad = null;
}
