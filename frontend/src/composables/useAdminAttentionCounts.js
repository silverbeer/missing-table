/**
 * useAdminAttentionCounts — powers the red dot + hover tooltip on the
 * global top-nav "Admin" link.
 *
 * Reactive singleton (same pattern as useSupportInbox; not Pinia). Polls
 * `GET /api/admin/attention/counts` every 60s while an admin is logged in.
 * Exposes a `total` ref + a `breakdown` ref the tooltip can render.
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

const POLL_MS = 60_000;

// ── Module-level singleton state ───────────────────────────────────────────

const total = ref(0);
const breakdown = ref({
  invite_requests: 0,
  channel_requests: 0,
  support_inbox: 0,
});
const lastError = ref(null);

let pollHandle = null;

// ── Public API ─────────────────────────────────────────────────────────────

export function useAdminAttentionCounts() {
  const authStore = useAuthStore();
  const isAdmin = computed(() => authStore.isAdmin.value);

  async function fetchCounts() {
    if (!isAdmin.value) {
      total.value = 0;
      return;
    }
    try {
      const resp = await fetch(
        `${getApiBaseUrl()}/api/admin/attention/counts`,
        {
          headers: authStore.getAuthHeaders(),
        }
      );
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();
      breakdown.value = {
        invite_requests: data.invite_requests || 0,
        channel_requests: data.channel_requests || 0,
        support_inbox: data.support_inbox || 0,
      };
      total.value = data.total || 0;
      lastError.value = null;
    } catch (e) {
      // Badge is best-effort — log and leave the previous count visible.
      console.warn('useAdminAttentionCounts: fetch failed', e);
      lastError.value = e.message;
    }
  }

  function startPolling() {
    if (pollHandle) return;
    fetchCounts();
    pollHandle = setInterval(fetchCounts, POLL_MS);
  }

  function stopPolling() {
    if (pollHandle) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  // Pluralizing helper for the tooltip — keeps the template clean.
  const tooltip = computed(() => {
    const parts = [];
    const b = breakdown.value;
    if (b.invite_requests > 0) {
      parts.push(
        `${b.invite_requests} invite request${b.invite_requests === 1 ? '' : 's'}`
      );
    }
    if (b.channel_requests > 0) {
      parts.push(
        `${b.channel_requests} channel request${b.channel_requests === 1 ? '' : 's'}`
      );
    }
    if (b.support_inbox > 0) {
      parts.push(
        `${b.support_inbox} unread support message${b.support_inbox === 1 ? '' : 's'}`
      );
    }
    return parts.length ? parts.join(' · ') : 'No items need attention';
  });

  return {
    total,
    breakdown,
    tooltip,
    lastError,
    fetchCounts,
    startPolling,
    stopPolling,
  };
}
