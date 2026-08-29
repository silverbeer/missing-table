/**
 * Which runtime caching strategy an API GET gets (SB-908).
 *
 * Split out of `sw.js` so the patterns are testable: a service worker module
 * cannot be imported in jsdom, and a regex that quietly stops matching is
 * exactly the kind of bug that shows up as "the score is wrong on my phone".
 *
 * Two classes:
 *
 * - **Reference** — age groups, seasons, divisions, leagues, match types,
 *   teams, clubs. These change when an admin edits them and never on their
 *   own, so StaleWhileRevalidate is right: instant paint, refresh behind.
 *
 * - **Results** — standings and tournaments. Both carry match scores, and both
 *   change the moment a match ends. Serving those stale means the paint that
 *   matters is the wrong one: on 2026-08-29 a tournament page kept showing a
 *   pre-match state after the API had already returned the final score.
 *   NetworkFirst instead — the cache is a fallback for a slow or absent
 *   network, not the default answer.
 *
 * Not cached at all (no route here): auth, live match state, writes.
 */

const REFERENCE_PATH =
  /\/api\/(teams|match-types|seasons|age-groups|divisions|leagues|clubs)(\/|\?|$)/;

const RESULTS_PATH = /\/api\/(standings|tournaments)(\/|\?|$)/;

/** Reference data: safe to serve from cache while it revalidates. */
export function isReferenceApi(pathAndSearch) {
  return REFERENCE_PATH.test(pathAndSearch);
}

/** Score-bearing data: network first, cache only as a fallback. */
export function isResultsApi(pathAndSearch) {
  return RESULTS_PATH.test(pathAndSearch);
}
