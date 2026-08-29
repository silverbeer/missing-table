# Caching Layers

Two independent caches sit between a reader and the database. Both are
invalidated on write, and both have bitten us when they weren't.

| Layer | Where | Holds | Invalidated by |
|-------|-------|-------|----------------|
| **DAO cache** | Redis, backend | `@dao_cache(...)` method results | `@invalidates_cache(<pattern>)` on the writing DAO method |
| **Service worker cache** | Browser, frontend | `GET` responses for the read APIs listed in `frontend/src/sw.js` | `bustApiCache()` after any successful write |

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

`frontend/src/sw.js` serves a fixed list of read APIs — standings, teams,
match-types, seasons, age-groups, divisions, leagues, tournaments, clubs — with
**StaleWhileRevalidate**: the cached copy is returned immediately and refreshed
in the background. That is what makes the app feel instant for fans, who only
ever read.

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

If you add an API to the `registerRoute` regex in `sw.js`, nothing else is
needed for invalidation — the whole-cache bust already covers it. If you change
the `cacheName`, update `API_CACHE_NAME` in `utils/swCache.js` to match; the
test in `__tests__/utils/swCache.spec.js` pins the two together.

## Related

- [Backend Structure](backend-structure.md) — DAO pattern
- [Standings](standings.md) — the most-cached read path
