/**
 * Match-row realtime subscription (SB-66).
 *
 * Thin Supabase Realtime subscriber for a single match's UPDATE events.
 * Used by MatchesView (per-row live updates) and MatchDetailView so a
 * score change posted from another device propagates without a manual
 * refresh.
 *
 * Mirrors the pattern in `useLiveMatch.js:151-220` but exposes just the
 * minimum surface needed for read-only consumers: one channel per
 * matchId, one callback that fires on UPDATE with the new row.
 *
 * Lifecycle:
 *   const handle = subscribeToMatch(matchId, (newRow) => {...});
 *   handle.unsubscribe();
 *
 * Consumers manage their own collection of handles — typically one per
 * in_progress match row, unsubscribed when the row transitions to
 * `completed` or when the view unmounts.
 */

import { supabase } from '../config/supabase';

/**
 * Subscribe to UPDATE broadcasts for a single match row.
 *
 * @param {number|string} matchId
 * @param {(newRow: object) => void} onUpdate - called with payload.new
 * @returns {{ unsubscribe: () => void, isConnected: () => boolean }}
 */
export function subscribeToMatch(matchId, onUpdate) {
  if (matchId == null) {
    throw new Error('subscribeToMatch requires a matchId');
  }
  if (typeof onUpdate !== 'function') {
    throw new Error('subscribeToMatch requires an onUpdate callback');
  }

  let connected = false;

  const channel = supabase
    .channel(`match-row:${matchId}`)
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'matches',
        filter: `id=eq.${matchId}`,
      },
      payload => {
        if (payload?.new) {
          onUpdate(payload.new);
        }
      }
    )
    .subscribe(status => {
      connected = status === 'SUBSCRIBED';
    });

  return {
    unsubscribe() {
      if (channel) {
        supabase.removeChannel(channel);
        connected = false;
      }
    },
    isConnected: () => connected,
  };
}
