/**
 * useSupportInbox composable (SB-35 Phase 3)
 *
 * Reactive singleton (matches the auth-store pattern — no Pinia) that backs
 * the Support Inbox admin UI. Holds thread list + active thread state, talks
 * to the Phase 2 admin API, and polls the unread-count badge.
 *
 * Exposes:
 *   threads, activeThread, messages, unreadCount, loading, sending, error
 *   loadThreads({status}), openThread(idOrMtN), closeThread(),
 *   sendReply(bodyText), setStatus(status), markAllRead(),
 *   fetchUnreadCount(), startPolling(), stopPolling()
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

const UNREAD_POLL_MS = 60_000;

// ── Module-level singleton state ───────────────────────────────────────────

const threads = ref({ items: [], nextCursor: null });
const activeThread = ref(null); // full thread row with .messages array
const unreadCount = ref(0);
const loading = ref(false);
const sending = ref(false);
const error = ref(null);
const currentStatus = ref('new,awaiting_admin'); // CSV status filter

let pollHandle = null;

// ── Helpers ────────────────────────────────────────────────────────────────

async function _apiFetch(path, { method = 'GET', body, signal } = {}) {
  const authStore = useAuthStore();
  const headers = authStore.getAuthHeaders();
  const opts = { method, headers, signal };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(`${getApiBaseUrl()}${path}`, opts);
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    const detail = data.detail || `request failed (${resp.status})`;
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  // 204s are rare on this surface; everything returns JSON.
  return resp.json();
}

function _isMtForm(value) {
  return /^MT-\d+$/i.test(String(value || '').trim());
}

// ── Public API ─────────────────────────────────────────────────────────────

export function useSupportInbox() {
  const isThreadOpen = computed(() => activeThread.value !== null);

  async function loadThreads({ status, cursor } = {}) {
    if (status) currentStatus.value = status;
    loading.value = true;
    error.value = null;
    try {
      const qs = new URLSearchParams({ status: currentStatus.value });
      if (cursor) qs.set('cursor', cursor);
      const data = await _apiFetch(`/api/admin/emails/threads?${qs}`);
      // Append on cursor-driven load-more, replace otherwise.
      if (cursor) {
        threads.value = {
          items: [...threads.value.items, ...(data.items || [])],
          nextCursor: data.next_cursor || null,
        };
      } else {
        threads.value = {
          items: data.items || [],
          nextCursor: data.next_cursor || null,
        };
      }
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  async function openThread(idOrMtN) {
    loading.value = true;
    error.value = null;
    try {
      const key = _isMtForm(idOrMtN) ? idOrMtN.toUpperCase() : idOrMtN;
      const data = await _apiFetch(
        `/api/admin/emails/threads/${encodeURIComponent(key)}`
      );
      activeThread.value = data;
    } catch (e) {
      error.value = e.message;
      activeThread.value = null;
    } finally {
      loading.value = false;
    }
  }

  function closeThread() {
    activeThread.value = null;
  }

  async function sendReply(bodyText) {
    if (!activeThread.value) {
      throw new Error('no active thread');
    }
    const trimmed = (bodyText || '').trim();
    if (!trimmed) {
      throw new Error('reply body is empty');
    }
    sending.value = true;
    error.value = null;
    try {
      const inserted = await _apiFetch(
        `/api/admin/emails/threads/${activeThread.value.id}/reply`,
        { method: 'POST', body: { body_text: trimmed } }
      );
      // Optimistically append + flip status pill.
      activeThread.value = {
        ...activeThread.value,
        status: 'awaiting_user',
        messages: [...(activeThread.value.messages || []), inserted],
      };
      // Reflect new status in the list cache too.
      _patchListEntry(activeThread.value.id, { status: 'awaiting_user' });
      return inserted;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      sending.value = false;
    }
  }

  async function setStatus(status) {
    if (!activeThread.value) return;
    const updated = await _apiFetch(
      `/api/admin/emails/threads/${activeThread.value.id}/status`,
      { method: 'PATCH', body: { status } }
    );
    activeThread.value = { ...activeThread.value, status: updated.status };
    _patchListEntry(activeThread.value.id, { status: updated.status });
  }

  async function markAllRead() {
    if (!activeThread.value) return;
    const result = await _apiFetch(
      `/api/admin/emails/threads/${activeThread.value.id}/read`,
      { method: 'PATCH' }
    );
    activeThread.value = {
      ...activeThread.value,
      unread_count: 0,
      messages: (activeThread.value.messages || []).map(m =>
        m.read_at ? m : { ...m, read_at: new Date().toISOString() }
      ),
    };
    _patchListEntry(activeThread.value.id, { unread_count: 0 });
    // Refresh badge — the count just dropped.
    fetchUnreadCount();
    return result;
  }

  async function fetchUnreadCount() {
    try {
      const data = await _apiFetch('/api/admin/emails/unread-count');
      unreadCount.value = data.count || 0;
    } catch (e) {
      // Badge is best-effort — don't surface its errors in the main UI.
      console.warn('useSupportInbox: unread-count fetch failed', e);
    }
  }

  function startPolling() {
    if (pollHandle) return;
    fetchUnreadCount();
    pollHandle = setInterval(fetchUnreadCount, UNREAD_POLL_MS);
  }

  function stopPolling() {
    if (pollHandle) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  function _patchListEntry(threadId, patch) {
    const items = threads.value.items || [];
    const idx = items.findIndex(t => t.id === threadId);
    if (idx === -1) return;
    const next = [...items];
    next[idx] = { ...next[idx], ...patch };
    threads.value = { ...threads.value, items: next };
  }

  return {
    // state
    threads,
    activeThread,
    unreadCount,
    loading,
    sending,
    error,
    currentStatus,
    isThreadOpen,
    // actions
    loadThreads,
    openThread,
    closeThread,
    sendReply,
    setStatus,
    markAllRead,
    fetchUnreadCount,
    startPolling,
    stopPolling,
  };
}
