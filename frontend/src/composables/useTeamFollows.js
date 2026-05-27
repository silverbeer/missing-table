/**
 * Team-follows composable (SB-55).
 *
 * Singleton reactive state shared by every FollowButton instance and the
 * NotificationsCard "Teams you follow" list. Mirrors the useAuthStore
 * pattern: module-level reactive state, useTeamFollows() returns the
 * same refs every call.
 *
 * Backend endpoints (already shipped via SB-51, all idempotent):
 *   GET    /api/users/me/team-follows           → { follows: [{ team_id, team, ... }] }
 *   POST   /api/users/me/team-follows           → 201 { team_id, following: true }
 *   DELETE /api/users/me/team-follows/{id}      → 204
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

  const isFollowing = teamId => state.followedTeamIds.has(Number(teamId));

  const follow = async teamId => {
    const id = Number(teamId);
    if (state.followedTeamIds.has(id)) return { success: true };

    // Optimistic
    state.followedTeamIds.add(id);
    state.error = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/team-follows`,
        {
          method: 'POST',
          body: JSON.stringify({ team_id: id }),
        }
      );
      // Refresh in background so the joined team/club data appears in
      // NotificationsCard's "Teams you follow" list.
      refresh();
      return { success: true };
    } catch (err) {
      state.followedTeamIds.delete(id);
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  const unfollow = async teamId => {
    const id = Number(teamId);
    if (!state.followedTeamIds.has(id)) return { success: true };

    // Optimistic
    state.followedTeamIds.delete(id);
    state.error = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/team-follows/${id}`,
        { method: 'DELETE' }
      );
      refresh();
      return { success: true };
    } catch (err) {
      state.followedTeamIds.add(id);
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  const toggle = async teamId => {
    return isFollowing(teamId) ? unfollow(teamId) : follow(teamId);
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
