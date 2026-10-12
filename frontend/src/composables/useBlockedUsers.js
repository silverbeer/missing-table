/**
 * useBlockedUsers — who the signed-in user has blocked in live chat (SB-1324).
 *
 * Reactive singleton (same pattern as useSupportInbox; not Pinia). App.vue
 * loads the list when a user signs in and clears it on sign-out. Event reads
 * already leave blocked authors' chat out; this set is what hides the chat
 * that arrives over realtime, and what blocking or reporting adds to at once.
 *
 * Blocking hides chat only. Goals, cards and subs stay visible.
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

// ── Module-level singleton state ───────────────────────────────────────────

// Rows from GET /api/users/me/blocks: { user_id, username, created_at }.
const blocks = ref([]);
const loaded = ref(false);
const loading = ref(false);
const error = ref(null);
// Ids hidden in this session — the loaded list plus anyone blocked since.
const blockedIds = ref(new Set());

// ── Public API ─────────────────────────────────────────────────────────────

export function useBlockedUsers() {
  const authStore = useAuthStore();

  function noteBlocked(userId) {
    if (!userId) return;
    blockedIds.value = new Set([...blockedIds.value, String(userId)]);
  }

  async function load() {
    loading.value = true;
    try {
      const rows = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/users/me/blocks`
      );
      blocks.value = Array.isArray(rows) ? rows : [];
      blockedIds.value = new Set(blocks.value.map(b => String(b.user_id)));
      loaded.value = true;
      error.value = null;
    } catch (e) {
      // Best-effort: the server still hides blocked chat on every read.
      console.warn('useBlockedUsers: load failed', e);
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  function clear() {
    blocks.value = [];
    blockedIds.value = new Set();
    loaded.value = false;
    error.value = null;
  }

  async function block(userId) {
    await authStore.apiRequest(`${getApiBaseUrl()}/api/users/${userId}/block`, {
      method: 'POST',
    });
    noteBlocked(userId);
  }

  async function unblock(userId) {
    await authStore.apiRequest(`${getApiBaseUrl()}/api/users/${userId}/block`, {
      method: 'DELETE',
    });
    const id = String(userId);
    blocks.value = blocks.value.filter(b => String(b.user_id) !== id);
    const next = new Set(blockedIds.value);
    next.delete(id);
    blockedIds.value = next;
  }

  /**
   * Report a chat message. The server also blocks its author for the
   * reporter, so this hides their chat without a second block call.
   * Returns the blocked author's id (null when their account is gone).
   */
  async function report(matchId, eventId, reason, details = null) {
    const response = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/matches/${matchId}/live/events/${eventId}/report`,
      { method: 'POST', body: JSON.stringify({ reason, details }) }
    );
    const authorId = response?.blocked_user_id ?? null;
    noteBlocked(authorId);
    return authorId;
  }

  return {
    blocks,
    blockedIds: computed(() => blockedIds.value),
    loaded,
    loading,
    error,
    load,
    clear,
    noteBlocked,
    block,
    unblock,
    report,
  };
}
