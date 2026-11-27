/**
 * useTournamentAnnouncements — the "new announcement" dot on the Tournaments
 * tab (SB-1797).
 *
 * An admin can set one line on a tournament ("Every MLS NEXT Fest match scored
 * live"). The tab shows a dot while any active tournament carries a line this
 * browser has not seen. Opening the tab marks every current line seen.
 *
 * "Seen" is a list of `<tournament_id>:<hash of text>` in localStorage, so an
 * edited announcement is new again and an untouched one stays quiet.
 *
 * Reactive singleton (same pattern as useAdminAttentionCounts). Fetches
 * `GET /api/tournaments` once per app load; any failure means no dot — the
 * badge is a nudge, never an error.
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export const SEEN_STORAGE_KEY = 'mt_seen_announcements';
// Enough for every tournament of a few seasons; the oldest fall off.
const MAX_SEEN = 100;

/** The announcement to show, or null. Blank is absent, never placeholder. */
export function announcementText(tournament) {
  const text = tournament?.announcement;
  if (typeof text !== 'string') return null;
  const trimmed = text.trim();
  return trimmed || null;
}

/** Short, stable hash (djb2, base 36). Not security: only change detection. */
export function hashText(text) {
  let h = 5381;
  for (let i = 0; i < text.length; i++) {
    h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

/** The seen-list key of a tournament's announcement, or null if it has none. */
export function announcementKey(tournament) {
  const text = announcementText(tournament);
  if (!text || tournament?.id == null) return null;
  return `${tournament.id}:${hashText(text)}`;
}

function readSeen() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SEEN_STORAGE_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.filter(k => typeof k === 'string')
      : [];
  } catch {
    return [];
  }
}

function writeSeen(keys) {
  try {
    localStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify(keys));
  } catch {
    // Private mode or a full quota: the dot just comes back next load.
  }
}

// ── Module-level singleton state ───────────────────────────────────────────

const tournaments = ref([]);
const seen = ref(readSeen());
let loadPromise = null;

const currentKeys = computed(() =>
  tournaments.value
    .filter(t => t?.is_active !== false)
    .map(announcementKey)
    .filter(Boolean)
);

const hasUnseen = computed(() => {
  const seenSet = new Set(seen.value);
  return currentKeys.value.some(k => !seenSet.has(k));
});

async function defaultFetch() {
  const authStore = useAuthStore();
  return authStore.apiRequest(`${getApiBaseUrl()}/api/tournaments`, {
    method: 'GET',
  });
}

/**
 * Load the tournament list once. Later calls return the same promise.
 * `fetcher` is injectable for tests; it resolves to the list.
 */
function load(fetcher = defaultFetch) {
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    try {
      const data = await fetcher();
      tournaments.value = Array.isArray(data) ? data : [];
    } catch (e) {
      console.warn('useTournamentAnnouncements: fetch failed', e);
      tournaments.value = [];
    }
  })();
  return loadPromise;
}

/** Every announcement currently showing is now seen. */
function markSeen() {
  const keys = currentKeys.value;
  if (!keys.length) return;
  const merged = [...seen.value.filter(k => !keys.includes(k)), ...keys];
  seen.value = merged.slice(-MAX_SEEN);
  writeSeen(seen.value);
}

/** Test-only: forget the loaded list and re-read localStorage. */
export function _resetTournamentAnnouncements() {
  tournaments.value = [];
  seen.value = readSeen();
  loadPromise = null;
}

export function useTournamentAnnouncements() {
  return { hasUnseen, load, markSeen };
}
