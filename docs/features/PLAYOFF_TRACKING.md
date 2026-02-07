# Playoff Tracking Feature

**Status**: In Progress
**Branch**: `feature/playoff-tracking`
**Started**: 2026-02-04

## Overview

Two parallel 8-team single elimination playoff brackets for Kick Futsal. All 16 teams from the two divisions (Bracket A and Bracket B) participate:

- **Upper Bracket**: Positions 1-4 from each division (8 teams)
- **Lower Bracket**: Positions 5-8 from each division (8 teams)

Each bracket uses cross-division seeding: Quarterfinals (4 games) → Semifinals (2 games) → Final (1 game). Total: 14 bracket slots, up to 14 matches.

### Key Concepts

| Term | Description |
|------|-------------|
| **Bracket Slot** | A position in the bracket that may or may not have a match assigned |
| **Bracket Tier** | Configurable name (e.g., "Gold", "Silver") — stored as free-form string in `bracket_tier` column |
| **Seeding** | Per tier: A1=1, B1=2, A2=3, B2=4, A3=5, B3=6, A4=7, B4=8 |
| **Source Slot** | Self-referencing FK linking a SF/Final slot to its feeder QF/SF slot |
| **Cross-Division** | Playoff matches have `division_id = NULL` — naturally excluded from league standings |
| **Scope** | Each bracket pair is scoped to `(league_id, season_id, age_group_id)` |

### Bracket Structure

Each tier (upper and lower) has the same structure:

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

### QF Matchups (same pattern for both tiers)

| Slot | Home | Away | Home Seed | Away Seed |
|------|------|------|-----------|-----------|
| QF1 | A1 | B4 | 1 | 8 |
| QF2 | B2 | A3 | 4 | 5 |
| QF3 | A2 | B3 | 3 | 6 |
| QF4 | B1 | A4 | 2 | 7 |

For the **upper bracket**, A1-A4 are division standings positions 1-4. For the **lower bracket**, A1-A4 are positions 5-8.

### Admin Workflow

1. **Configure**: Admin selects league/season/age group, then configures:
   - **Division A/B**: Which two divisions to use for the bracket
   - **First Round Date**: When quarterfinal matches will be scheduled
   - **Tier Names**: Custom names for each bracket (e.g., "Gold" and "Silver" instead of "upper"/"lower")
2. **Generate**: Click "Generate Playoff Bracket" → system reads current standings, creates bracket slots and QF matches with configured settings
3. **Score**: Admin enters scores for QF matches via standard match edit flow (AdminMatches)
4. **Advance**: After a match is completed, admin clicks "Advance Winner" on the Playoffs tab → system creates next-round match when both feeder slots are complete
5. **Forfeit**: If a team forfeits, admin/manager clicks "Forfeit" on a scheduled or live match → selects the forfeiting team → system sets score to 0-3, marks match as `forfeit`, and automatically advances the winner
6. **Repeat**: Continue through SF and Final rounds for both tiers
7. **Reset**: Admin can delete entire bracket (both tiers) and start over if needed

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
    bracket_tier VARCHAR(10) NOT NULL DEFAULT 'upper' CHECK (bracket_tier IN ('upper', 'lower')),
    match_id INTEGER REFERENCES matches(id) ON DELETE SET NULL,
    home_seed INTEGER,
    away_seed INTEGER,
    home_source_slot_id INTEGER REFERENCES playoff_bracket_slots(id),
    away_source_slot_id INTEGER REFERENCES playoff_bracket_slots(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(league_id, season_id, age_group_id, bracket_tier, round, bracket_position)
);

CREATE INDEX idx_playoff_bracket_league_season_ag_tier
    ON playoff_bracket_slots(league_id, season_id, age_group_id, bracket_tier);

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

- **`bracket_tier`** — Free-form string (e.g., "Gold", "Silver", "Bronze") that distinguishes between parallel brackets. Part of the unique constraint so each tier has its own set of positions.
- **`match_id`** is nullable — SF/Final slots exist before their matches are created. `ON DELETE SET NULL` preserves bracket structure if a match is deleted.
- **`home_source_slot_id` / `away_source_slot_id`** are self-referencing FKs that define bracket progression (e.g., "winner of QF1 feeds into SF1 home"). Enables automatic advancement without hardcoding bracket structure. Inherently tier-scoped since they reference specific slot IDs.
- **`home_seed` / `away_seed`** store original seeding for display purposes only.

### Generate Bracket Logic

1. Validate enough teams for configured tiers (e.g., 8 teams if using positions 1-8)
2. For each configured tier:
   - Slice standings based on tier's `start_position` and `end_position`
   - Create 7 `playoff_bracket_slots` rows (4 QF + 2 SF + 1 Final) with custom `bracket_tier` name
   - Create `matches` rows for QF round only (teams known), with `match_type_id = 4` (Playoff), `match_status = 'scheduled'`, `division_id = NULL`, and configured `start_date`
3. SF/Final matches created later by `advance_winner` when both feeder slots complete
4. Total: 14 slots, 8 QF matches (for standard 2-tier configuration)

### API Request Model

```python
class BracketTierConfig(BaseModel):
    name: str           # e.g., "Gold", "Silver"
    start_position: int # 1 for positions 1-4, 5 for positions 5-8
    end_position: int   # 4 for positions 1-4, 8 for positions 5-8

class GenerateBracketRequest(BaseModel):
    league_id: int
    season_id: int
    age_group_id: int
    division_a_id: int
    division_b_id: int
    start_date: str                   # ISO date for QF matches (e.g., "2026-02-15")
    tiers: list[BracketTierConfig]    # Tier configurations
```

### Team ID Resolution

`calculate_standings()` returns team names (strings), not team IDs. The generate endpoint queries teams by division to build a name→ID mapping rather than modifying the standings function.

### Cross-Division Match Filtering

Playoff matches set `division_id = NULL`. The existing `filter_same_division_matches()` only runs when `division_id` is provided, so playoff matches are naturally excluded from regular league standings. No changes to the standings engine needed.

### Forfeit Handling

A team can forfeit a playoff match (when status is `scheduled` or `live`). The flow:

1. Admin/manager clicks "Forfeit" button on the bracket slot
2. Selects which team is forfeiting via radio buttons
3. Backend sets: `match_status = 'forfeit'`, forfeiting team score = 0, non-forfeiting team score = 3, `forfeit_team_id` = forfeiting team
4. `advance_winner()` is called automatically — the winner advances to the next round

**API Endpoints:**
- `POST /api/playoffs/forfeit` — team/club managers (permission-checked)
- `POST /api/admin/playoffs/forfeit` — admin (unrestricted)

Both accept `{ slot_id: int, forfeit_team_id: int }`.

**Database:** The `matches` table has a `forfeit_team_id` column (nullable FK → `teams`) with a CHECK constraint ensuring it's only set when `match_status = 'forfeit'` and references a participant team.

**UI:** Forfeited matches show an orange border, and the forfeiting team's score displays "(F)" next to the 0.

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
| `supabase-local/migrations/20260205000000_add_playoff_bracket_slots.sql` | Created | Base table migration |
| `supabase-local/migrations/20260205100000_add_bracket_tier.sql` | Created | Add `bracket_tier` column + updated constraints |
| `supabase-local/migrations/20260205110000_bracket_tier_name.sql` | Created | Remove CHECK constraint, allow free-form tier names |
| `backend/models/playoffs.py` | Created | Pydantic models with `bracket_tier` and `scheduled_kickoff` fields |
| `backend/dao/playoff_dao.py` | Created | PlayoffDAO with dual-tier bracket generation, advancement, and deletion |
| `frontend/src/components/PlayoffBracket.vue` | Created | Public dual-tier bracket visualization |
| `frontend/src/components/admin/AdminPlayoffs.vue` | Created | Admin playoff management with dual-tier display |
| `frontend/src/components/admin/BracketSlotCard.vue` | Created | Inline date/time editing card for bracket slots |
| `supabase-local/migrations/20260207000000_add_forfeit_status.sql` | Created | Add `forfeit` enum value + `forfeit_team_id` column |
| `backend/app.py` | Modified | 4 new endpoints + DAO instantiation + 2 forfeit endpoints |
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
| 2026-02-04 | Phases 1-7 implemented (single bracket) |
| 2026-02-05 | Upgraded to dual-tier brackets (upper + lower), all 16 teams participate |
| 2026-02-05 | Added configurable bracket generation: custom tier names, start date, division selection |
| 2026-02-07 | Added forfeit support: forfeit button, 0-3 scoring, auto-advancement, orange UI indicators |
