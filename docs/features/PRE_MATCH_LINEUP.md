# Pre-Match Starting Lineup

## Overview

Admins, club managers, and team managers can set starting lineups for **scheduled** matches before they go live. Lineups set pre-match automatically carry over when the match transitions to live status (same database row).

## How It Works

1. Navigate to a **scheduled** match detail view
2. Click **"Starting Lineup"** to expand the lineup section
3. Select the home or away team tab
4. Choose a formation and assign players from the team roster
5. Click **"Save Lineup"** to persist

## Permissions

| Role | Access |
|------|--------|
| Admin | All matches |
| Club Manager | All matches (their club's teams) |
| Team Manager | Only matches involving their team |
| Regular User | No access |

## Architecture

### Shared Composable

The `useMatchLineup.js` composable provides shared roster/lineup logic used by both:
- **`MatchDetailView.vue`** - Pre-match lineup (scheduled matches)
- **`useLiveMatch.js`** - Live match lineup management

This avoids code duplication and ensures both paths use the same API calls.

### Component Reuse

The existing `LineupManager.vue` component (from the live match feature) is reused directly. It is already decoupled from live match logic and accepts props for roster, lineup data, and save callbacks.

### API Endpoints Used

- `GET /api/teams/{team_id}/roster?season_id={id}` - Fetch team roster
- `GET /api/matches/{match_id}/lineup/{team_id}` - Fetch existing lineup
- `PUT /api/matches/{match_id}/lineup/{team_id}` - Save/update lineup

No backend changes were needed - these endpoints work for any match status.

## Files

| File | Role |
|------|------|
| `frontend/src/composables/useMatchLineup.js` | Shared roster/lineup composable |
| `frontend/src/composables/useLiveMatch.js` | Delegates to useMatchLineup |
| `frontend/src/components/MatchDetailView.vue` | Pre-match lineup UI |
| `frontend/src/components/live/LineupManager.vue` | Reusable lineup editor |
