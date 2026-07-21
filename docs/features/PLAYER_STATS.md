# Player Stats Feature

**Status**: In Development
**Branch**: `feature/player-stats`
**Started**: 2026-01-16

## Overview

Create a roster management system with player statistics tracking. Players can exist on team rosters independent of MT accounts. Jersey number + team uniquely identifies a player for stat tracking.

### Key Concepts

| Term | Description |
|------|-------------|
| **Roster Entry** | A player on a team roster (may or may not have MT account) |
| **Identifier** | Jersey number + team_id + season_id (unique) |
| **Account Link** | `players.user_profile_id` links to MT account (nullable) |
| **Display** | Players without accounts show "#23", with accounts show full name |

### Stats Tracked (Phase 1)

- Games Played
- Games Started
- Minutes
- Goals

---

## Position Taxonomy (SB-284, July 2026)

Player `positions` is an **ordered array of specific position codes** — the
first entry is the player's **primary** position. Each code belongs to exactly
one broad group, used for lineup-slot filtering:

| Group | Codes |
|-------|-------|
| GK  | GK |
| DEF | CB, LB, RB, LWB, RWB |
| MID | CDM, CM, CAM, LM, RM |
| FWD | LW, RW, ST, CF |

Retired side-specific codes are remapped on write and were migrated in the DB:
LCB/RCB → CB, LCM/RCM → CM. Formation *slot* codes in `match_lineups.positions`
(LCB, RST, futsal FIX/PIV/…) are a separate vocabulary and unaffected.

Source of truth: `frontend/src/constants/positions.js`, hand-mirrored in
`backend/constants/positions.py` (parity enforced by
`backend/tests/unit/test_position_constants.py`). Backend request models use
the shared `Positions` Pydantic type, which validates codes and dedupes while
preserving order.

---

## Unified Admin Players View (SB-286, July 2026)

**Admin → Teams & Players → Players** shows two merged populations:

- **Account players** — `user_profiles` with role `team-player` (signed up
  via invite). `source: 'account'`.
- **Roster-only players** — `players`-table rows with no linked account
  (`user_profile_id IS NULL`), added by jersey number. `source: 'roster'`,
  badged "No account" in the UI. Scoped to the current season by default
  (`season_id` query param overrides).

Linked roster rows are excluded from the roster population automatically, so
nobody appears twice. The tab's **+ Add Player** button creates a roster
entry via `POST /api/teams/{id}/roster` (team, season, age group, jersey,
optional names/positions) — same endpoint as the team Roster manager.
Roster-only rows are edited via the team roster; account rows via
Edit/Teams actions.

---

## Invite Claim by Jersey Number (SB-287, July 2026)

A `team_player` invite with a jersey number **claims an existing roster
spot** when the player registers — it never auto-creates roster rows.

Flow:
1. Admin/team manager adds the player to the roster (jersey number, per age
   group), then creates the invite. **Creation validates** that an unclaimed
   roster spot exists for `(team, season, age group, jersey)` and pins the
   exact `player_id` on the invitation; the **season is stored on the
   invitation** (`invitations.season_id`, default = current season) so
   redemption never guesses from the date.
2. `GET /api/invites/validate/{code}` returns `claimable` + `claim_reason`
   for team_player invites. Signup (password and OAuth) checks this **before
   creating the auth user** — an unclaimable invite blocks registration with
   an actionable message instead of minting an orphan account.
3. On redemption the claim sets `players.user_profile_id` with an atomic
   `IS NULL` guard (a race with another claimant fails loudly instead of
   stealing the link) and writes the `player_team_history` entry.

Legacy invites (jersey but no `player_id`/`season_id`) fall back to a
current-season lookup at redemption, with the same block-on-miss behavior.

---

## Lineup Position Filtering (SB-288, July 2026)

Clicking a formation slot in the lineup editor partitions the player picker:

- **Suggested** — players whose position group (via `SLOT_TO_GROUP` +
  `groupForPosition`) matches the slot's group, primary-position matches
  first. A GK slot suggests goalkeepers; an LCB slot suggests defenders.
- **Other players** — everyone else, including players with no positions set
  (quick-added rosters stay fully selectable — it's a soft partition, never
  a hard filter).

Formation slot codes are a separate vocabulary from player position codes
(slots keep side-specific codes like LCB/RST); `SLOT_TO_GROUP` in
`frontend/src/constants/positions.js` maps all soccer + futsal slot codes to
groups, coverage pinned by both the backend parity test and
`LineupManager.positions.spec.js`.

---

## Implementation Checklist

### Phase 1: Database Schema

- [x] Create `players` table migration
  - [x] Fields: id, team_id, season_id, jersey_number, first_name, last_name, user_profile_id, positions, age_group_id, is_active
  - [x] Unique constraint: (team_id, season_id, age_group_id, jersey_number) NULLS NOT DISTINCT (SB-285)
  - [x] Indexes: team_season, user_profile
- [x] Create `player_match_stats` table migration
  - [x] Fields: id, player_id, match_id, started, minutes_played, goals
  - [x] Unique constraint: (player_id, match_id)
- [x] Add `player_id` column to `invitations` table
- [x] Add `player_id` column to `match_events` table
- [x] Apply migrations to local Supabase
- [x] Verify all constraints and indexes

### Phase 2: Backend - Roster Management

- [x] Create `backend/dao/roster_dao.py`
  - [x] `get_team_roster(team_id, season_id)`
  - [x] `get_player_by_id(player_id)`
  - [x] `get_player_by_jersey(team_id, season_id, jersey_number)`
  - [x] `create_player(...)`
  - [x] `bulk_create_players(team_id, season_id, players)`
  - [x] `update_player(player_id, ...)`
  - [x] `delete_player(player_id)`
  - [x] `link_user_to_player(player_id, user_profile_id)`
  - [x] `update_jersey_number(player_id, new_number)`
  - [x] `bulk_renumber(team_id, season_id, changes)`
- [x] Create `backend/models/roster.py`
  - [x] `RosterPlayerCreate`
  - [x] `RosterPlayerUpdate`
  - [x] `BulkRosterCreate`
  - [x] `RosterPlayerResponse`
  - [x] `JerseyNumberUpdate`
  - [x] `BulkRenumberRequest`
- [x] Add roster API endpoints to `app.py`
  - [x] `GET /api/teams/{team_id}/roster`
  - [x] `POST /api/teams/{team_id}/roster`
  - [x] `POST /api/teams/{team_id}/roster/bulk`
  - [x] `PUT /api/teams/{team_id}/roster/{player_id}`
  - [x] `DELETE /api/teams/{team_id}/roster/{player_id}`
  - [x] `PUT /api/teams/{team_id}/roster/{player_id}/number`
  - [x] `POST /api/teams/{team_id}/roster/renumber`
- [ ] Write backend tests for roster endpoints

### Phase 3: Backend - Invite Flow Enhancement

- [x] Modify `InviteService.create_invitation()` to accept `player_id`
- [x] Modify `InviteService.redeem_invitation()` to link user to player
- [x] Update invite API endpoint to accept `player_id`
- [ ] Test invite → account → player linking flow

### Phase 4: Backend - Player Stats

- [x] Create `backend/dao/player_stats_dao.py`
  - [x] `get_or_create_match_stats(player_id, match_id)`
  - [x] `increment_goals(player_id, match_id)`
  - [x] `decrement_goals(player_id, match_id)`
  - [x] `set_started(player_id, match_id, started)`
  - [x] `update_minutes(player_id, match_id, minutes)`
  - [x] `get_player_season_stats(player_id, season_id)`
  - [x] `get_team_stats(team_id, season_id)`
- [x] Modify goal endpoint in `app.py`
  - [x] Accept `player_id` in addition to `player_name`
  - [x] Validate player is on match team
  - [x] Create match_event with player_id
  - [x] Update player_match_stats
- [x] Add stats API endpoints
  - [x] `GET /api/roster/{player_id}/stats`
  - [x] `GET /api/teams/{team_id}/stats`
- [ ] Write backend tests for stats

### Phase 5: Frontend - Roster Manager

- [x] Create `frontend/src/components/roster/RosterManager.vue`
  - [x] Display roster list with player cards
  - [x] Individual add player form
  - [x] Bulk import modal (paste jersey numbers)
  - [x] Edit player modal (name, positions)
  - [x] Change jersey number
  - [ ] Bulk renumber mode (deferred - low priority)
  - [x] Delete player confirmation
  - [x] Send invite button per player
  - [x] Visual indicator: account linked vs not
- [x] Integrate into AdminTeams.vue (modal approach)
- [x] Pass age_group_id to RosterManager for invite creation

### Phase 6: Frontend - Live Game Enhancement

- [x] Modify `LiveAdminControls.vue`
  - [x] Fetch rosters for both teams when goal modal opens
  - [x] Replace free-text input with roster dropdown
  - [x] Filter roster by selected team
  - [x] Show "#number name" format in dropdown
  - [x] Fallback to text input when "Other" selected or no roster
- [x] Modify `useLiveMatch.js`
  - [x] Add `fetchTeamRosters()` method
  - [x] Update `postGoal()` to send `player_id`
- [x] Update `LiveMatchView.vue` to pass `fetchTeamRosters` to controls
- [ ] Test goal entry flow end-to-end

### Phase 7: Frontend - Stats Display

- [x] Add individual stats to `PlayerProfile.vue`
  - [x] Games Played
  - [x] Games Started
  - [x] Minutes
  - [x] Goals
- [ ] Create team stats view (optional, deferred)
  - [ ] Roster with stats columns
  - [ ] Sort by different stats

### Phase 8: Post-Match Stats Editor

- [x] Database migration: Add `substitution` event type and `player_out_id` column to `match_events`
- [x] Backend models: `PostMatchGoal`, `PostMatchSubstitution`, `PlayerStatEntry`, `BatchPlayerStatsUpdate`
- [x] DAO additions: `get_team_match_stats()`, `batch_update_stats()`, `player_out_id` in `create_event()`
- [x] API endpoints:
  - [x] `POST /api/matches/{id}/post-match/goal` - Record goal event
  - [x] `DELETE /api/matches/{id}/post-match/goal/{event_id}` - Remove goal
  - [x] `POST /api/matches/{id}/post-match/substitution` - Record substitution
  - [x] `DELETE /api/matches/{id}/post-match/substitution/{event_id}` - Remove substitution
  - [x] `GET /api/matches/{id}/post-match/stats/{team_id}` - Get player stats
  - [x] `PUT /api/matches/{id}/post-match/stats/{team_id}` - Batch update stats
- [x] Frontend composable: `usePostMatchStats.js`
- [x] Frontend components: `PostMatchEditor.vue`, `TeamStatsPanel.vue`
- [x] Integration: Added to `MatchDetailView.vue` for completed matches

### Phase 9: Testing & Polish

- [ ] End-to-end test: Create roster → Send invite → Accept → Link verified
- [ ] End-to-end test: Live game → Score goal → Stats updated
- [ ] Run full test suite
- [ ] Run linters (frontend + backend)
- [ ] Manual QA on local environment

---

## Technical Details

### Database Schema

```sql
-- players table
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season_id INTEGER NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    jersey_number INTEGER NOT NULL CHECK (jersey_number >= 1 AND jersey_number <= 99),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    user_profile_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    positions TEXT[],  -- ordered specific codes; first = primary (see taxonomy below)
    age_group_id INTEGER REFERENCES age_groups(id),  -- squad within umbrella teams
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    -- SB-285: jerseys unique per age group so umbrella clubs (e.g. IFA
    -- fielding U13-U19 on one team row) can reuse numbers across squads.
    -- NULLS NOT DISTINCT: rows without an age group behave as one squad.
    UNIQUE NULLS NOT DISTINCT (team_id, season_id, age_group_id, jersey_number)
);

-- player_match_stats table
CREATE TABLE player_match_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    started BOOLEAN DEFAULT false,
    minutes_played INTEGER DEFAULT 0,
    goals INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, match_id)
);
```

### Display Name Logic

```python
def get_display_name(player: dict) -> str:
    """Return full name if available, otherwise jersey number."""
    if player.get('user_profile_id'):
        # Has linked account - could fetch name from user_profiles
        pass
    if player.get('first_name') or player.get('last_name'):
        return f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
    return f"#{player['jersey_number']}"
```

### Bulk Renumber Algorithm

To handle jersey number swaps without constraint violations:

```python
def bulk_renumber(team_id, season_id, changes):
    """
    changes = [{player_id: 1, new_number: 10}, {player_id: 2, new_number: 7}]
    """
    # Step 1: Set all affected players to negative numbers (temporary)
    for change in changes:
        update_number(change['player_id'], -change['player_id'])

    # Step 2: Set final numbers
    for change in changes:
        update_number(change['player_id'], change['new_number'])
```

---

## Files Modified/Created

| File | Status | Description |
|------|--------|-------------|
| `supabase/migrations/20260117000001_create_players_table.sql` | New | Players table |
| `supabase/migrations/20260117000002_create_player_match_stats.sql` | New | Stats table |
| `supabase/migrations/20260117000003_add_player_id_to_invitations.sql` | New | Invite linking |
| `supabase/migrations/20260117000004_add_player_id_to_match_events.sql` | New | Event linking |
| `backend/dao/roster_dao.py` | New | Roster data access |
| `backend/dao/player_stats_dao.py` | New | Stats data access |
| `backend/models/roster.py` | New | Pydantic models |
| `backend/services/invite_service.py` | Modified | Add player_id support |
| `backend/app.py` | Modified | New endpoints, modify goal posting |
| `frontend/src/components/roster/RosterManager.vue` | New | Roster management UI |
| `frontend/src/components/admin/AdminTeams.vue` | Modified | Integrates RosterManager with age_group_id |
| `frontend/src/components/live/LiveAdminControls.vue` | Modified | Roster dropdown for goal scorer |
| `frontend/src/components/live/LiveMatchView.vue` | Modified | Pass fetchTeamRosters to controls |
| `frontend/src/composables/useLiveMatch.js` | Modified | fetchTeamRosters(), postGoal with player_id |
| `backend/dao/match_dao.py` | Modified | Add season_id to live match state |
| `frontend/src/components/profiles/PlayerProfile.vue` | Modified | Show individual player stats (Games Played, Games Started, Minutes, Goals) |
| `supabase/migrations/20260120000001_add_jersey_number_to_invitations.sql` | New | Add jersey_number to invitations |
| `frontend/src/components/admin/AdminInvites.vue` | Modified | Add jersey number input for team_player invites |
| `backend/api/invites.py` | Modified | Accept jersey_number in invite creation |
| `backend/dao/roster_dao.py` | Modified | Add get_player_by_user_profile_id() method |
| `supabase/migrations/20260208000000_add_substitution_event_type.sql` | New | Add substitution event type and player_out_id |
| `backend/models/post_match.py` | New | Post-match stats Pydantic models |
| `backend/dao/match_event_dao.py` | Modified | Add player_out_id parameter |
| `backend/dao/player_stats_dao.py` | Modified | Add get_team_match_stats(), batch_update_stats() |
| `backend/app.py` | Modified | Post-match goal, substitution, stats endpoints |
| `frontend/src/composables/usePostMatchStats.js` | New | Post-match stats composable |
| `frontend/src/components/PostMatchEditor.vue` | New | Post-match stats editor component |
| `frontend/src/components/post-match/TeamStatsPanel.vue` | New | Team stats panel sub-component |
| `frontend/src/components/MatchDetailView.vue` | Modified | Integrate PostMatchEditor for completed matches |

---

## Open Questions

- [ ] Should stats be visible to everyone or just team members?
- [ ] Do we need goalkeeper-specific stats (saves, clean sheets)?
- [ ] How to handle players who move teams mid-season?

---

## Change Log

| Date | Change |
|------|--------|
| 2026-01-16 | Initial plan created |
| 2026-01-17 | Phase 1 complete: Database migrations for players, player_match_stats, invitations.player_id, match_events.player_id |
| 2026-01-17 | Phase 2 complete: RosterDAO, models, and API endpoints |
| 2026-01-17 | Phase 3 complete: InviteService enhanced with player_id support |
| 2026-01-17 | Phase 4 complete: PlayerStatsDAO, goal endpoint modified, stats API endpoints added |
| 2026-01-20 | Phase 5 complete: RosterManager.vue integrated into AdminTeams, fixed age_group_id passing for invites |
| 2026-01-20 | Phase 6 complete: Live game goal entry now uses roster dropdown with player_id tracking |
| 2026-01-20 | Phase 7 complete: Individual player stats (Games Played, Games Started, Minutes, Goals) displayed in PlayerProfile.vue |
| 2026-01-20 | Enhancement: Added jersey_number field to AdminInvites.vue - creates roster entry when invite is redeemed |
| 2026-02-08 | Phase 8 complete: Post-match stats editor - goals, substitutions, and player stats for completed matches |
