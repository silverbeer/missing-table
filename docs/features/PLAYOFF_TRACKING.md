# Playoff Tracking Feature

**Status**: Planned
**Branch**: `feature/playoff-tracking`
**Started**: 2026-02-04

## Overview

8-team single elimination playoff bracket for Kick Futsal. Top 4 teams from each of the two divisions (Bracket A and Bracket B) are seeded into a cross-division bracket: Quarterfinals (4 games) → Semifinals (2 games) → Final (1 game).

### Key Concepts

| Term | Description |
|------|-------------|
| **Bracket Slot** | A position in the bracket that may or may not have a match assigned |
| **Seeding** | A1=1, B1=2, A2=3, B2=4, A3=5, B3=6, A4=7, B4=8 |
| **Source Slot** | Self-referencing FK linking a SF/Final slot to its feeder QF/SF slot |
| **Cross-Division** | Playoff matches have `division_id = NULL` — naturally excluded from league standings |
| **Scope** | Each bracket is scoped to `(league_id, season_id, age_group_id)` |

### Bracket Structure

```
Quarterfinals          Semifinals           Final
 +--------------+
 | A1 vs B4     |--+
 +--------------+  |  +--------------+
                   +--| SF1          |
 +--------------+  |  |              |--+
 | B2 vs A3     |--+  +--------------+  |
 +--------------+                       |  +--------------+
                                        +--| Final        |
 +--------------+                       |  |              |
 | A2 vs B3     |--+  +--------------+  |  +--------------+
 +--------------+  +--| SF2          |--+
                   |  |              |
 +--------------+  |  +--------------+
 | B1 vs A4     |--+
 +--------------+
```

### QF Matchups

| Slot | Home | Away | Home Seed | Away Seed |
|------|------|------|-----------|-----------|
| QF1 | A1 | B4 | 1 | 8 |
| QF2 | B2 | A3 | 4 | 5 |
| QF3 | A2 | B3 | 3 | 6 |
| QF4 | B1 | A4 | 2 | 7 |

### Admin Workflow

1. **Generate**: Admin selects league/season/age group → clicks "Generate Playoff Bracket" → system reads current standings, takes top 4 from each division, creates 7 bracket slots + 4 QF matches
2. **Score**: Admin enters scores for QF matches via standard match edit flow (AdminMatches)
3. **Advance**: After a match is completed, admin clicks "Advance Winner" on the Playoffs tab → system creates next-round match when both feeder slots are complete
4. **Repeat**: Continue through SF and Final rounds
5. **Reset**: Admin can delete entire bracket and start over if needed

---

## Implementation Checklist

### Phase 1: Database Schema

- [ ] Create `playoff_bracket_slots` table migration
  - [ ] Fields: id, league_id, season_id, age_group_id, round, bracket_position, match_id, home_seed, away_seed, home_source_slot_id, away_source_slot_id, created_at, updated_at
  - [ ] CHECK constraint on round: `('quarterfinal', 'semifinal', 'final')`
  - [ ] UNIQUE constraint: `(league_id, season_id, age_group_id, round, bracket_position)`
  - [ ] Self-referencing FKs: `home_source_slot_id`, `away_source_slot_id`
  - [ ] `match_id` nullable with `ON DELETE SET NULL`
  - [ ] Index on `(league_id, season_id, age_group_id)`
  - [ ] RLS policies: SELECT for all, INSERT/UPDATE/DELETE for admins
- [ ] Apply migration to local Supabase
- [ ] Verify constraints and indexes

### Phase 2: Backend — Pydantic Models

- [ ] Create `backend/models/playoffs.py`
  - [ ] `PlayoffBracketSlot` — full slot with denormalized match data (team names, scores, status)
  - [ ] `GenerateBracketRequest` — league_id, season_id, age_group_id, division_a_id, division_b_id
  - [ ] `AdvanceWinnerRequest` — slot_id

### Phase 3: Backend — PlayoffDAO

- [ ] Create `backend/dao/playoff_dao.py` (extends BaseDAO)
  - [ ] `get_bracket(league_id, season_id, age_group_id)` — returns all slots with joined match/team data
  - [ ] `generate_bracket(league_id, season_id, age_group_id, standings_a, standings_b, division_a_id, division_b_id)` — creates 7 slots + 4 QF matches in transaction
  - [ ] `advance_winner(completed_slot_id)` — determines winner, updates next-round slot, creates match when both teams known
  - [ ] `delete_bracket(league_id, season_id, age_group_id)` — removes all bracket slots
  - [ ] `link_match_to_slot(slot_id, match_id)` — link existing match to a bracket slot
  - [ ] `create_slot(slot_data)` — create single bracket slot
  - [ ] `update_slot(slot_id, data)` — update a bracket slot
  - [ ] Cache pattern: `PLAYOFF_CACHE_PATTERN = "mt:dao:playoffs:*"`

### Phase 4: Backend — API Endpoints

- [ ] Add DAO instantiation in `app.py` (~line 190)
- [ ] `GET /api/playoffs/bracket` — query params: league_id, season_id, age_group_id; auth: logged-in user
- [ ] `POST /api/admin/playoffs/generate` — body: GenerateBracketRequest; auth: admin; validates ≥4 teams per division
- [ ] `POST /api/admin/playoffs/advance` — body: AdvanceWinnerRequest; auth: admin
- [ ] `DELETE /api/admin/playoffs/bracket` — query params: league_id, season_id, age_group_id; auth: admin

### Phase 5: Frontend — AdminPlayoffs.vue

- [ ] Create `frontend/src/components/admin/AdminPlayoffs.vue`
  - [ ] League/Season/Age Group selection dropdowns
  - [ ] "Generate Playoff Bracket" button (when no bracket exists)
  - [ ] Auto-detect division IDs from league's divisions
  - [ ] Bracket visualization with admin controls
  - [ ] "Advance Winner" button on completed slots
  - [ ] "Edit Match" link navigating to AdminMatches
  - [ ] "Reset Bracket" button to delete and start over
- [ ] Register in `AdminPanel.vue`
  - [ ] Add `{ id: 'playoffs', name: 'Playoffs', adminOnly: true }` to `allAdminSections` (~line 180)
  - [ ] Import and render AdminPlayoffs component

### Phase 6: Frontend — PlayoffBracket.vue

- [ ] Create `frontend/src/components/PlayoffBracket.vue`
  - [ ] Props: leagueId, seasonId, ageGroupId
  - [ ] 3-column CSS grid layout (QF → SF → Final)
  - [ ] Matchup cards with team names, seed labels, scores, winner highlight
  - [ ] "TBD" for undetermined slots
  - [ ] Connector lines via CSS borders/pseudo-elements
  - [ ] Mobile responsive (vertical stack on small screens)

### Phase 7: Frontend — LeagueTable Integration

- [ ] Modify `frontend/src/components/LeagueTable.vue`
  - [ ] Check bracket existence on load (lightweight API call)
  - [ ] Add "Show Playoff Bracket" / "Show Standings" toggle button
  - [ ] Conditionally render `<PlayoffBracket>` or standings table

### Phase 8: Testing & Polish

- [ ] End-to-end test: Generate bracket from standings
- [ ] End-to-end test: Enter QF scores → advance winners → SF matches created
- [ ] End-to-end test: Complete bracket through to Final
- [ ] Test reset bracket flow
- [ ] Run linters (frontend + backend)
- [ ] Manual QA on local environment

---

## Technical Details

### Database Schema

```sql
CREATE TABLE public.playoff_bracket_slots (
    id SERIAL PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(id),
    season_id INTEGER NOT NULL REFERENCES seasons(id),
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id),
    round VARCHAR(20) NOT NULL CHECK (round IN ('quarterfinal', 'semifinal', 'final')),
    bracket_position INTEGER NOT NULL,
    match_id INTEGER REFERENCES matches(id) ON DELETE SET NULL,
    home_seed INTEGER,
    away_seed INTEGER,
    home_source_slot_id INTEGER REFERENCES playoff_bracket_slots(id),
    away_source_slot_id INTEGER REFERENCES playoff_bracket_slots(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(league_id, season_id, age_group_id, round, bracket_position)
);

CREATE INDEX idx_playoff_bracket_league_season_ag
    ON playoff_bracket_slots(league_id, season_id, age_group_id);

-- RLS: visible to all, writable by admins
ALTER TABLE public.playoff_bracket_slots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "playoff_bracket_slots_select"
    ON public.playoff_bracket_slots FOR SELECT USING (true);

CREATE POLICY "playoff_bracket_slots_admin_insert"
    ON public.playoff_bracket_slots FOR INSERT WITH CHECK (public.is_admin());

CREATE POLICY "playoff_bracket_slots_admin_update"
    ON public.playoff_bracket_slots FOR UPDATE USING (public.is_admin());

CREATE POLICY "playoff_bracket_slots_admin_delete"
    ON public.playoff_bracket_slots FOR DELETE USING (public.is_admin());
```

### Column Design Notes

- **`match_id`** is nullable — SF/Final slots exist before their matches are created. `ON DELETE SET NULL` preserves bracket structure if a match is deleted.
- **`home_source_slot_id` / `away_source_slot_id`** are self-referencing FKs that define bracket progression (e.g., "winner of QF1 feeds into SF1 home"). Enables automatic advancement without hardcoding bracket structure.
- **`home_seed` / `away_seed`** store original seeding for display purposes only.

### Pydantic Models

```python
class PlayoffBracketSlot(BaseModel):
    id: int
    league_id: int
    season_id: int
    age_group_id: int
    round: str
    bracket_position: int
    match_id: int | None = None
    home_seed: int | None = None
    away_seed: int | None = None
    home_source_slot_id: int | None = None
    away_source_slot_id: int | None = None
    # Denormalized from linked match
    home_team_name: str | None = None
    away_team_name: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    match_status: str | None = None
    match_date: str | None = None

class GenerateBracketRequest(BaseModel):
    league_id: int
    season_id: int
    age_group_id: int
    division_a_id: int
    division_b_id: int

class AdvanceWinnerRequest(BaseModel):
    slot_id: int
```

### Generate Bracket Logic

1. Create 7 `playoff_bracket_slots` rows in a transaction
2. QF slots (positions 1–4) with seeding from standings
3. SF slots with `home_source_slot_id`/`away_source_slot_id` pointing to QF slots
4. Final slot with source slots pointing to SF1 and SF2
5. Create `matches` rows for QF round only (teams known), with `match_type_id = 4` (Playoff), `match_status = 'scheduled'`, `division_id = NULL`
6. SF/Final matches created later by `advance_winner` when both feeder slots complete

### Team ID Resolution

`calculate_standings()` returns team names (strings), not team IDs. The generate endpoint queries teams by division to build a name→ID mapping rather than modifying the standings function.

### Cross-Division Match Filtering

Playoff matches set `division_id = NULL`. The existing `filter_same_division_matches()` only runs when `division_id` is provided, so playoff matches are naturally excluded from regular league standings. No changes to the standings engine needed.

### Existing Infrastructure (No Changes Needed)

- Match type "Playoff" (ID: 4) already in seed data
- Kick Futsal league (ID: 34) with Bracket A (ID: 36) and Bracket B (ID: 37) already configured
- `filter_by_match_type()` in standings.py handles match type filtering
- Match creation/editing endpoints in app.py
- MatchesView.vue already shows playoff matches via existing "Playoff" filter button

---

## Files Modified/Created

| File | Status | Description |
|------|--------|-------------|
| `supabase-local/migrations/20260205000000_add_playoff_bracket_slots.sql` | New | Database migration for playoff_bracket_slots table |
| `backend/models/playoffs.py` | New | Pydantic models (PlayoffBracketSlot, GenerateBracketRequest, AdvanceWinnerRequest) |
| `backend/dao/playoff_dao.py` | New | PlayoffDAO with bracket CRUD, generation, and advancement logic |
| `frontend/src/components/PlayoffBracket.vue` | New | Public bracket visualization (3-column grid with connector lines) |
| `frontend/src/components/admin/AdminPlayoffs.vue` | New | Admin playoff management (generate, advance, reset) |
| `backend/app.py` | Modified | 4 new endpoints + DAO instantiation |
| `frontend/src/components/AdminPanel.vue` | Modified | Register Playoffs tab in allAdminSections |
| `frontend/src/components/LeagueTable.vue` | Modified | Add bracket toggle when playoffs exist |

---

## Open Questions

- [ ] Should a 3rd place match be supported? (Common in youth sports but not in initial scope)
- [ ] Cache invalidation: match updates via existing endpoints don't invalidate playoff cache. Accept slight staleness for now?
- [ ] How to handle ties in playoff matches? (Overtime, penalty kicks, or admin manually decides?)
- [ ] Should bracket be visible to non-logged-in users? (Current design requires authentication)

---

## Change Log

| Date | Change |
|------|--------|
| 2026-02-04 | Initial plan created |
