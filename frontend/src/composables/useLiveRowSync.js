/**
 * Keep a list of match rows current while some of them are live (SB-909).
 *
 * A view that loads its matches once and then sits there goes stale the moment
 * a match ends somewhere else — another device, another tab, the live-scoring
 * screen. That is what happened to the Tournaments tab on 2026-08-29: the API
 * had the final score immediately, the open page never asked again.
 *
 * Two mechanisms, because neither alone is enough:
 *
 * 1. **Realtime** — one Supabase subscription per live row, merged into the
 *    list as UPDATEs arrive. Cheap and instant, but only while the socket is
 *    connected, and only for rows that were live when we subscribed.
 * 2. **Refresh on return** — a full refetch when the tab becomes visible
 *    again. Covers everything realtime missed: a dropped socket, a phone
 *    asleep in a pocket, a match that went live after the page loaded.
 *
 * Subscriptions are reconciled whenever the list changes and torn down on
 * unmount.
 */

import { getCurrentInstance, onUnmounted, watch } from 'vue';
import { subscribeToMatch } from './useMatchRealtime';

/**
 * @param {import('vue').Ref|import('vue').ComputedRef} matches - list of match
 *   objects; each needs `id` and `match_status`.
 * @param {(newRow: object) => void} applyUpdate - called with the raw `matches`
 *   row from a realtime UPDATE. The payload carries only real columns, so the
 *   consumer must merge rather than replace (joined display fields would be
 *   lost otherwise).
 * @param {object} [options]
 * @param {() => void} [options.onReturn] - called when the tab becomes visible
 *   again. Usually the view's own refetch.
 */
export function useLiveRowSync(matches, applyUpdate, { onReturn } = {}) {
  const subs = new Map(); // matchId → handle

  function liveIdsOf(list) {
    return new Set(
      (list || [])
        .filter(m => m?.match_status === 'live' && m?.id != null)
        .map(m => m.id)
    );
  }

  function reconcile(list) {
    const live = liveIdsOf(list);
    for (const [id, handle] of subs) {
      if (!live.has(id)) {
        handle.unsubscribe();
        subs.delete(id);
      }
    }
    for (const id of live) {
      if (subs.has(id)) continue;
      try {
        subs.set(id, subscribeToMatch(id, applyUpdate));
      } catch (err) {
        // Realtime is an enhancement, not the data path. A misconfigured or
        // unreachable socket must not take the view down with it — the
        // refresh-on-return half still keeps the page honest.
        console.error('Live row subscription failed:', err);
      }
    }
  }

  function teardown() {
    for (const handle of subs.values()) handle.unsubscribe();
    subs.clear();
  }

  const stopWatch = watch(matches, reconcile, { immediate: true });

  const onVisibility = () => {
    if (typeof document !== 'undefined' && !document.hidden) onReturn?.();
  };
  if (onReturn && typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibility);
  }

  const stop = () => {
    stopWatch();
    teardown();
    if (onReturn && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibility);
    }
  };

  // Called from a composable a test drives directly, there is no instance to
  // hang the hook on — and Vue warns about that rather than ignoring it.
  if (getCurrentInstance()) onUnmounted(stop);

  // Exposed for tests and for callers that manage their own lifetime.
  return { stop, subscribedIds: () => [...subs.keys()] };
}
