/**
 * Notification-preferences composable (SB-57).
 *
 * Singleton reactive state for per-event push opt-in flags. Mirrors the
 * useTeamFollows.js pattern from SB-55 — module-level reactive state, every
 * call to useNotificationPreferences() returns the same refs.
 *
 * Backend (idempotent, lazy-default on the server):
 *   GET /api/users/me/notification-preferences   → { preferences: {event_type: bool, ...} }
 *   PUT /api/users/me/notification-preferences   body: { preferences: {...} } → same shape
 *
 * Defaults must mirror backend/notifications/preferences.py so the UI can
 * render correctly before the first GET completes.
 */

import { reactive, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export const EVENT_TYPES = Object.freeze([
  'kickoff',
  'goal',
  'halftime',
  'fulltime',
  'yellow_card',
  'red_card',
]);

export const DEFAULT_PREFERENCES = Object.freeze({
  kickoff: true,
  goal: true,
  halftime: true,
  fulltime: true,
  yellow_card: false,
  red_card: false,
});

const state = reactive({
  preferences: { ...DEFAULT_PREFERENCES },
  loaded: false,
  loading: false,
  error: null,
});

let inflightLoad = null;

async function fetchPreferences() {
  const authStore = useAuthStore();
  if (!authStore.isAuthenticated.value) {
    state.preferences = { ...DEFAULT_PREFERENCES };
    state.loaded = true;
    return;
  }

  state.loading = true;
  state.error = null;
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/users/me/notification-preferences`
    );
    state.preferences = {
      ...DEFAULT_PREFERENCES,
      ...(data?.preferences || {}),
    };
    state.loaded = true;
  } catch (err) {
    state.error = err.message || String(err);
    state.preferences = { ...DEFAULT_PREFERENCES };
  } finally {
    state.loading = false;
  }
}

export function useNotificationPreferences() {
  const authStore = useAuthStore();

  const ensureLoaded = () => {
    if (state.loaded || state.loading) return inflightLoad || Promise.resolve();
    inflightLoad = fetchPreferences().finally(() => {
      inflightLoad = null;
    });
    return inflightLoad;
  };

  const refresh = () => {
    inflightLoad = fetchPreferences().finally(() => {
      inflightLoad = null;
    });
    return inflightLoad;
  };

  const setPreference = async (eventType, enabled) => {
    if (!EVENT_TYPES.includes(eventType)) {
      return { success: false, error: `Unknown event_type: ${eventType}` };
    }
    const prev = state.preferences[eventType];
    if (prev === enabled) return { success: true };

    // Optimistic
    state.preferences = { ...state.preferences, [eventType]: enabled };
    state.error = null;
    try {
      const data = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/notification-preferences`,
        {
          method: 'PUT',
          body: JSON.stringify({ preferences: { [eventType]: enabled } }),
        }
      );
      // Backend echoes the merged state — trust it over the optimistic guess
      // in case other devices changed prefs in parallel.
      if (data?.preferences) {
        state.preferences = {
          ...DEFAULT_PREFERENCES,
          ...data.preferences,
        };
      }
      return { success: true };
    } catch (err) {
      state.preferences = { ...state.preferences, [eventType]: prev };
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  // Combined cards toggle — sets yellow_card and red_card together.
  // Backend stores them separately so SB-58/future per-card prefs stay
  // possible without a schema change.
  const setCards = async enabled => {
    const prevYellow = state.preferences.yellow_card;
    const prevRed = state.preferences.red_card;
    if (prevYellow === enabled && prevRed === enabled) {
      return { success: true };
    }

    state.preferences = {
      ...state.preferences,
      yellow_card: enabled,
      red_card: enabled,
    };
    state.error = null;
    try {
      const data = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/notification-preferences`,
        {
          method: 'PUT',
          body: JSON.stringify({
            preferences: { yellow_card: enabled, red_card: enabled },
          }),
        }
      );
      if (data?.preferences) {
        state.preferences = {
          ...DEFAULT_PREFERENCES,
          ...data.preferences,
        };
      }
      return { success: true };
    } catch (err) {
      state.preferences = {
        ...state.preferences,
        yellow_card: prevYellow,
        red_card: prevRed,
      };
      state.error = err.message || String(err);
      return { success: false, error: state.error };
    }
  };

  return {
    preferences: computed(() => state.preferences),
    cardsEnabled: computed(
      () => state.preferences.yellow_card || state.preferences.red_card
    ),
    loaded: computed(() => state.loaded),
    loading: computed(() => state.loading),
    error: computed(() => state.error),
    ensureLoaded,
    refresh,
    setPreference,
    setCards,
  };
}

// Test-only: reset module-level singleton between tests.
export function _resetNotificationPreferencesForTest() {
  state.preferences = { ...DEFAULT_PREFERENCES };
  state.loaded = false;
  state.loading = false;
  state.error = null;
  inflightLoad = null;
}
