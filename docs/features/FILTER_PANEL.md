# Collapsible filter panel (Table + Matches)

**Tickets:** SB-1714, SB-1715 · **Android equivalent:** SB-1680 (`MatchFilters.kt`)

The Table and Matches tabs put their filters (age group, division, competition,
season, conference) in one collapsible panel, `frontend/src/components/ui/FilterPanel.vue`.

| State | Header shows | Body |
|-------|--------------|------|
| Open | "Filters" + chevron | every filter row |
| Closed | one-line summary of what narrows the list, e.g. `2026-2027 · U15 · Flex · Northeast, Empire` | hidden (`v-show`, so filter state is untouched) |

- **Every breakpoint.** The old Matches collapse was mobile-only (`lg:hidden`).
- **Remembered per tab and per viewer** (`mt.filterPanel.v1.<view>.<userId|anon>`),
  and on the account when signed in — see below. Open until the viewer first
  closes it. A `localStorage` failure (Safari private mode) means "open", never
  an error. The pre-SB-1715 per-browser key is handed to the first viewer who
  reads it, then removed.
- **Summary** is built by `utils/filterSummary.js`: parts that narrow nothing are
  dropped — "All" competitions, no conference picked. A multi-select names up to
  two values, then counts (`3 conferences`).
- **Matches:** Match of the Week and Week Navigation sit *outside* the panel, so
  collapsing filters never hides them.

Tests: `__tests__/components/FilterPanel.spec.js`, `__tests__/utils/filterSummary.spec.js`.

## Remembered filters follow the account (SB-1715)

The selected filters (`useFilterMemory`, SB-1112) and the panel's open/closed
state are kept in two places:

| Where | Key | Who |
|-------|-----|-----|
| Browser `localStorage` | `mt.filters.v1.<view>.<userId\|anon>` | everyone |
| `user_profiles.filter_memory` (jsonb) | `{ "<view>": { filters, panel_open, saved_at } }` | signed-in viewers |

- **Read:** the account copy arrives with the profile from `/api/auth/me`
  (Redis-cached, `mt:dao:players:profile:<id>`). `load()` returns whichever copy
  has the later `savedAt` (client clock, ms); the browser copy wins ties. An
  account copy of `filters: null` that is newer means "forgotten elsewhere".
- **Write:** `PUT /api/auth/filter-memory/{table|matches}` with
  `{ filters?, panel_open?, saved_at }`. Debounced 1.5 s per view and viewer, so
  a burst of chip clicks is one request; flushed on `pagehide` (`keepalive`).
  A failure is ignored — the browser copy already has it.
- **Storage:** the `set_filter_memory(user_id, view, patch)` RPC merges one
  view's patch in a single `UPDATE` — and, since SB-1722, merges `filters` key by
  key, so each platform sends only its own fields. The cross-platform field list
  is [filter-memory-format.md](../03-architecture/filter-memory-format.md), so Table and Matches cannot drop each
  other's entry. It is its own column, not a key in `preferences`, so a filter
  save and a Profile save never overwrite each other. Service role only.
- **Cache:** a filter save clears only that viewer's cached profile. It does
  **not** use `update_user_profile`, whose `invalidates_cache("mt:dao:players:*")`
  would clear every user's.
- **Validation** (`backend/filter_memory.py`): the filters are opaque to the
  backend — the component checks every id against what it fetched before
  applying it — but are bounded: ≤16 keys, scalar or ≤50-item scalar lists,
  strings ≤64 chars.
- Saving a default age group in Profile still clears both views' memory, now on
  the account too.

Tests: `backend/tests/unit/test_filter_memory.py`,
`frontend/src/__tests__/composables/useFilterMemory.spec.js`.
