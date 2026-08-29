/**
 * Service-worker cache busting for writes (SB-902).
 *
 * The service worker serves the read APIs listed in `sw.js` with
 * StaleWhileRevalidate: a GET returns the cached copy immediately and
 * refreshes in the background. That is right for fans, and wrong the instant
 * the same session has just written: an admin POSTs a tournament match, the
 * component re-fetches `/api/tournaments/{id}`, and the SW hands back the
 * response it cached *before* the write. The row only appears after a reload.
 *
 * So: after any successful write, drop the whole runtime cache. The breadth is
 * deliberate. Working out which cached URLs a given write invalidates means
 * re-deriving the backend's own invalidation rules in the client, and getting
 * that wrong reintroduces exactly this bug in a narrower place. Only admins and
 * team managers write, the cache holds nothing but reference/read data, and
 * every entry refills in a single request — there is nothing to be clever with.
 */

// Must match the `cacheName` of the runtime route in src/sw.js.
export const API_CACHE_NAME = 'mt-reference-and-standings-v1';

/**
 * Delete the service worker's cached API responses.
 *
 * Safe to call anywhere: no service worker, no Cache API (older browsers,
 * some private-mode contexts), or an already-empty cache are all no-ops.
 *
 * @returns {Promise<boolean>} true if a cache was actually deleted.
 */
export async function bustApiCache() {
  if (typeof caches === 'undefined' || !caches?.delete) return false;
  try {
    return await caches.delete(API_CACHE_NAME);
  } catch {
    // A failed bust must never fail the write that triggered it.
    return false;
  }
}
