/**
 * Live activity stream helpers (SB-1329).
 *
 * Chat no longer streams over Realtime: clients cannot read chat rows. When
 * a match's chat changes, the client re-reads the newest page of events from
 * the API and merges it into what it already shows.
 */

/**
 * Merge a freshly fetched newest-first page into the current list.
 *
 * Inside the page's window the fetch is authoritative: rows it returns are
 * added or replaced, and rows it no longer returns (deleted messages) are
 * dropped. Older rows outside the window — pages loaded with "Load more" —
 * are kept as they are. A page shorter than `limit` is the whole stream, so
 * its window is everything.
 */
export function mergeEventWindow(current, fetched, limit) {
  const fresh = Array.isArray(fetched) ? fetched : [];
  const complete = fresh.length < limit;
  const oldestFetched = fresh.length
    ? Math.min(...fresh.map(e => e.id))
    : -Infinity;
  const inWindow = event => complete || event.id >= oldestFetched;

  const byId = new Map();
  for (const event of current) {
    if (!inWindow(event)) byId.set(event.id, event);
  }
  for (const event of fresh) byId.set(event.id, event);

  return [...byId.values()].sort((a, b) => b.id - a.id);
}
