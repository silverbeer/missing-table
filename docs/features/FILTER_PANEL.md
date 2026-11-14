# Collapsible filter panel (Table + Matches)

**Ticket:** SB-1714 · **Android equivalent:** SB-1680 (`MatchFilters.kt`)

The Table and Matches tabs put their filters (age group, division, competition,
season, conference) in one collapsible panel, `frontend/src/components/ui/FilterPanel.vue`.

| State | Header shows | Body |
|-------|--------------|------|
| Open | "Filters" + chevron | every filter row |
| Closed | one-line summary of what narrows the list, e.g. `2026-2027 · U15 · Flex · Northeast, Empire` | hidden (`v-show`, so filter state is untouched) |

- **Every breakpoint.** The old Matches collapse was mobile-only (`lg:hidden`).
- **Remembered per tab** in `localStorage` (`mt.filterPanel.v1.table`,
  `mt.filterPanel.v1.matches`). Open until the viewer first closes it. A
  `localStorage` failure (Safari private mode) means "open", never an error.
- **Summary** is built by `utils/filterSummary.js`: parts that narrow nothing are
  dropped — "All" competitions, no conference picked. A multi-select names up to
  two values, then counts (`3 conferences`).
- **Matches:** Match of the Week and Week Navigation sit *outside* the panel, so
  collapsing filters never hides them.

Tests: `__tests__/components/FilterPanel.spec.js`, `__tests__/utils/filterSummary.spec.js`.
