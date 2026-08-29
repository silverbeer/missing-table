# Caching Layers

Two independent caches sit between a reader and the database. Both are
invalidated on write, and both have bitten us when they weren't.

| Layer | Where | Holds | Invalidated by |
|-------|-------|-------|----------------|
| **DAO cache** | Redis, backend | `@dao_cache(...)` method results | `@invalidates_cache(<pattern>)` on the writing DAO method |
| **Service worker cache** | Browser, frontend | `GET` responses for the read APIs matched in `frontend/src/utils/swRoutes.js` | `bustApiCache()` after any successful write |

## DAO cache (Redis)

`dao/base_dao.py` provides `@dao_cache("key:template:{arg}")` for reads and
`@invalidates_cache("mt:dao:<resource>:*")` for writes. Keys are shared across
pods, so a write on one pod clears the cache for all of them.

Rules:

- Every cached read's key includes every argument that changes the result —
  `include_test` in particular, so the test partition never leaks to a real
  viewer.
- A write invalidates every pattern its result can appear under, not just its
  own resource. `create_tournament_match` clears both `tournaments:*` and
  `matches:*`.
- **Direct SQL through Supabase Studio bypasses this entirely** — no decorator
  runs. Pair a Studio fix with an API write or `redis-cli DEL`.

## Service worker cache (browser)

`frontend/src/sw.js` caches two classes of read API, split by whether the data
can change on its own (`frontend/src/utils/swRoutes.js` holds the patterns, so
they are testable):

| Class | APIs | Strategy | Cache |
|-------|------|----------|-------|
| **Reference** | teams, match-types, seasons, age-groups, divisions, leagues, clubs | StaleWhileRevalidate | `mt-reference-and-standings-v1` |
| **Results** | standings, tournaments | NetworkFirst (4s timeout) | `mt-results-v1` |

Reference data changes only when an admin edits it, so serving the cached copy
first and refreshing behind it is what makes the app feel instant for fans, who
only ever read.

Results are different: standings and tournament payloads carry match scores and
change the moment a match ends. Serving those stale means the paint that matters
is the wrong one — on 2026-08-29 a tournament page kept showing a pre-match
state long after the API had the final score (SB-908). Network first, with the
cache as the fallback for a slow or absent connection rather than the default
answer.

Not cached at all: auth, writes, `/api/matches*` and live match state.

It is also a read-your-write hazard for the people who write. An admin adds a
tournament match, the component re-fetches `/api/tournaments/{id}`, and the
service worker answers from the copy it cached *before* the write — the new row
appears to have been dropped until a reload (SB-902).

So **every successful write drops the whole runtime cache**, via
`bustApiCache()` in `frontend/src/utils/swCache.js`:

- `apiCall()` in `stores/auth.js` calls it after any non-`GET` that succeeds —
  which covers almost every write in the app, including the one that only
  succeeded after a token refresh.
- A handful of write paths use raw `fetch` (multipart logo uploads, a couple of
  older admin forms). Those call `bustApiCache()` themselves. **If you add a
  write that does not go through the auth store, call it.**

The bust is deliberately whole-cache rather than per-URL. Working out which
cached URLs a given write invalidates means re-deriving the backend's
invalidation rules in the client, and getting that wrong reintroduces this bug
somewhere narrower and harder to see. Only admins and team managers write, the
cache holds nothing but read data, and every entry refills in one request.

`bustApiCache()` is a no-op wherever the Cache API is missing or throws (dev
without a service worker, older browsers, some private-mode contexts) — a failed
bust must never fail the write that triggered it.

### Adding a route to the service worker cache

Add the path to `isReferenceApi` or `isResultsApi` in `utils/swRoutes.js` —
results if the response carries anything that changes without an admin touching
it (scores, standings, live state), reference otherwise. Nothing else is needed
for invalidation; the whole-cache bust already covers both caches.

If you change or add a `cacheName`, update `API_CACHE_NAMES` in
`utils/swCache.js` to match — a cache nothing busts is a cache that serves
pre-write data forever. `__tests__/utils/swCache.spec.js` pins the names
together, and `__tests__/utils/swRoutes.spec.js` pins the patterns.

## Staying current without a reload

A cache that is never re-read is still stale. The Tournaments tab loaded its
matches once and had no refresh trigger at all, so a match ending on another
device left the open page wrong until someone reloaded it (SB-909).

`composables/useLiveRowSync.js` is the shared answer, and both mechanisms are
needed:

- **Realtime** — one Supabase subscription per row whose `match_status` is
  `live`, reconciled as the list changes. Instant, but only while the socket is
  up and only for rows that were live when we subscribed.
- **Refresh on return** — a refetch when the tab becomes visible again. Covers a
  dropped socket, a phone asleep in a pocket, and a match that went live after
  the page loaded.

Realtime payloads carry raw `matches` columns only, so a consumer must **merge**
them into the row rather than replace it — the joined team, club and age-group
objects the row renders from are not in the payload.

## Related

- [Backend Structure](backend-structure.md) — DAO pattern
- [Standings](standings.md) — the most-cached read path
