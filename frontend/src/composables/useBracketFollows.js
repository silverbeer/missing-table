/**
 * Bracket-follows composable.
 *
 * Singleton reactive state shared by every bracket FollowButton. Mirrors
 * useTeamFollows: module-level reactive state, useBracketFollows() returns
 * the same refs every call. A bracket is keyed by the tuple
 * (tournament_id, tournament_group, age_group_id), joined into a string key.
 *
 * Backend endpoints (idempotent):
 *   GET    /api/users/me/bracket-follows  → { follows: [{ tournament_id, tournament_group, age_group_id, ... }] }
 *   POST   /api/users/me/bracket-follows  → 201 { ..., following: true }
 *   DELETE /api/users/me/bracket-follows?tournament_id=&tournament_group=&age_group_id=  → 204
 */

import { reactive, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

const state = reactive({
  followedKeys: new Set(),
  follows: [],
  loaded: false,
  loading: false,
  error: null,
});

let inflightLoad = null;

// Stable string key for a bracket tuple.
function bracketKey(tournamentId, tournamentGroup, ageGroupId) {
  return `${Number(tournamentId)}:${tournamentGroup}:${Number(ageGroupId)}`;
}

async function fetchFollows() {
  const authStore = useAuthStore();
  if (!authStore.isAuthenticated.value) {
    state.followedKeys = new Set();
    state.follows = [];
    state.loaded = true;
    return;
  }

  state.loading = true;
  state.error = null;
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/users/me/bracket-follows`
    );
    const rows = data?.follows || [];
    state.follows = rows;
    state.followedKeys = new Set(
      rows.map(r =>
        bracketKey(r.tournament_id, r.tournament_group, r.age_group_id)
      )
    );
    state.loaded = true;
  } catch (err) {
    state.error = err.message || String(err);
    state.followedKeys = new Set();
    state.follows = [];
  } finally {
    state.loading = false;
  }
}

export function useBracketFollows() {
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

  const isFollowing = (tournamentId, tournamentGroup, ageGroupId) =>
    state.followedKeys.has(
      bracketKey(tournamentId, tournamentGroup, ageGroupId)
    );

  const follow = async (tournamentId, tournamentGroup, ageGroupId) => {
    const key = bracketKey(tournamentId, tournamentGroup, ageGroupId);
    if (state.followedKeys.has(key)) return { success: true };

    // Optimistic
    state.followedKeys.add(key);
    state.error = null;
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/bracket-follows`,
        {
          method: 'POST',
          body: JSON.stringify({
            tournament_id: Number(tournamentId),
            tournament_group: tournamentGroup,
            age_group_id: Number(ageGroupId),
          }),
        }
      );
      refresh();
      return { success: true };
    } catch (err) {
      state.followedKeys.delete(key);
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  const unfollow = async (tournamentId, tournamentGroup, ageGroupId) => {
    const key = bracketKey(tournamentId, tournamentGroup, ageGroupId);
    if (!state.followedKeys.has(key)) return { success: true };

    // Optimistic
    state.followedKeys.delete(key);
    state.error = null;
    try {
      const qs = new URLSearchParams({
        tournament_id: String(Number(tournamentId)),
        tournament_group: tournamentGroup,
        age_group_id: String(Number(ageGroupId)),
      });
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/bracket-follows?${qs.toString()}`,
        { method: 'DELETE' }
      );
      refresh();
      return { success: true };
    } catch (err) {
      state.followedKeys.add(key);
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  const toggle = async (tournamentId, tournamentGroup, ageGroupId) => {
    return isFollowing(tournamentId, tournamentGroup, ageGroupId)
      ? unfollow(tournamentId, tournamentGroup, ageGroupId)
      : follow(tournamentId, tournamentGroup, ageGroupId);
  };

  return {
    follows: computed(() => state.follows),
    followedKeys: computed(() => state.followedKeys),
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
export function _resetBracketFollowsForTest() {
  state.followedKeys = new Set();
  state.follows = [];
  state.loaded = false;
  state.loading = false;
  state.error = null;
  inflightLoad = null;
}
