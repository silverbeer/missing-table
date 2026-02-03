# BUG: MyClub Tab Shows "No Team Assigned" Despite Player Being on Teams

**Status**: Fixed
**Discovered**: 2026-02-03
**Fixed**: 2026-02-03
**Severity**: Medium - affects team-player users viewing their team roster

---

## Summary

When a player (e.g., `gabe35`) is added to teams via the admin/team-manager UI, the MyClub tab still shows "No Team Assigned". The team memberships are correctly stored in `player_team_history` but the frontend checks `user_profiles.team_id`, which is never updated by the "add player to team" flow.

## Steps to Reproduce

1. Log in as admin or team manager
2. Add a player (e.g., gabe35) to a team (e.g., IFA Academy) via the roster manager
3. Log in as the player (gabe35 / play123)
4. Navigate to the MyClub tab
5. **Expected**: Shows team roster for IFA Academy
6. **Actual**: Shows "No Team Assigned"

## Root Cause

There is a disconnect between two systems:

### Where team membership is stored (write path)
The "add player to team" flow writes to `player_team_history`:
```
player_team_history:
  player_id = <user UUID>
  team_id = 123 (IFA Academy)
  season_id = 3
  is_current = true
```

### Where team membership is read (read path)
`TeamRosterRouter.vue` checks `user_profiles.team_id`:
```javascript
// frontend/src/components/profiles/TeamRosterRouter.vue:98
const hasTeam = computed(() => {
  return !!authStore.state.profile?.team_id;
});
```

The `user_profiles.team_id` field is **only** set during the invite-code signup flow (`backend/app.py:385-396`), not when a player is added to a team through the roster manager.

## Data Evidence (from prod, 2026-02-03)

**gabe35's user_profiles:**
- `team_id`: NULL
- `club_id`: NULL
- `role`: team-player

**gabe35's player_team_history (2 entries):**
- team_id=123 (IFA Academy), season_id=3, is_current=true
- team_id=184 (IFA Elite Futsal 2012 White), season_id=3, is_current=true

## Proposed Fix

### Option A: Fix the read path (Recommended)

Update the MyClub tab to use `player_team_history` as the source of truth instead of (or in addition to) `user_profiles.team_id`.

**Files to change:**
1. **Backend** - Add endpoint or extend `/api/auth/me` to return team memberships from `player_team_history` where `is_current = true`
2. **Frontend** - `frontend/src/components/profiles/TeamRosterRouter.vue` - Check `player_team_history` data instead of only `user_profiles.team_id`

**Why this is better:** A player can be on multiple teams (gabe35 is on 2). `user_profiles.team_id` is a single integer and can't represent multiple team memberships.

### Option B: Fix the write path

Update the "add player to team" flow to also set `user_profiles.team_id`. This is simpler but doesn't handle the multiple-teams case well.

### Option C: Both

Use `player_team_history` as primary source of truth for the MyClub tab, and also keep `user_profiles.team_id` in sync as a convenience/primary-team field.

## Key Files

| File | Role |
|------|------|
| `frontend/src/components/profiles/TeamRosterRouter.vue` | MyClub tab - checks `team_id` (line 98) |
| `frontend/src/stores/auth.js` | Stores profile from `/api/auth/me` |
| `backend/app.py` | `/api/auth/me` endpoint (line ~1529) |
| `backend/dao/player_dao.py` | `get_user_profile_with_relationships()` (line 27) |
| `backend/services/invite_service.py` | Only place that sets `user_profiles.team_id` (during invite redemption) |
| `supabase-local/migrations/00000000000000_schema.sql` | Schema for `player_team_history` and `user_profiles` |

## Fix Applied

**Option A implemented**: The read path was fixed to use `player_team_history` as the source of truth.

### Changes Made

1. **`backend/app.py`** (`/api/auth/me` endpoint): For `team-player` users, the response now includes a `current_teams` array populated from `player_team_history` (via `player_dao.get_all_current_player_teams()`). This returns all teams where `is_current=true`, supporting multi-team players.

2. **`frontend/src/components/profiles/TeamRosterRouter.vue`**: The `hasTeam` computed property now checks both `profile.team_id` (legacy path from invite signup) and `profile.current_teams.length > 0` (from `player_team_history`). Either being truthy allows the player through to the roster view.

No changes were needed in `TeamRosterPage.vue` since it already fetches current teams from `/api/auth/profile/teams/current` and uses `player_team_history` data.

## Additional Context

- `user_profiles.team_id` is set correctly when a user signs up via an invite code (the signup flow in `app.py:385-396` copies `team_id` from the invitation)
- The roster manager adds players to teams via `player_team_history` but never touches `user_profiles.team_id`
- Test users (tom_ifa, tom_ifa_fan) have `team_id` set because they're created by `seed_test_users.sh` which directly sets it
