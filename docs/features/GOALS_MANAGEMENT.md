# Goals Management Admin Panel

**Status**: Complete
**Started**: 2026-02-08

## Overview

Admin panel tab for managing goal events -- primarily for fixing mistakes such as deleting erroneous goals or correcting goal times. Also fixes a bug where deleting a goal didn't update player stats.

## Features

### Admin Panel - Goals Tab

A new "Goals" tab in the admin panel allows admins and club managers to:

- **View** all goal events with match context (teams, date, season, age group)
- **Filter** by season, age group, and match type
- **Edit** goal time (match minute, extra time) and player name
- **Delete** goals with automatic score and player stats adjustment

### Bug Fix: Player Stats on Goal Deletion

Previously, deleting a goal event only decremented the match score but did not update `player_match_stats`. Now, when a goal with a tracked `player_id` is deleted, the player's goal count is also decremented.

## API Endpoints

### `GET /api/admin/goals`

List goal events with optional filters. Requires match management permission.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `season_id` | int | Filter by season |
| `age_group_id` | int | Filter by age group |
| `match_type_id` | int | Filter by match type |
| `team_id` | int | Filter by scoring team |
| `limit` | int | Max results (default 100, max 500) |
| `offset` | int | Pagination offset |

### `PATCH /api/admin/goals/{event_id}`

Update a goal event's time or player. Requires match management permission.

**Request Body (all fields optional):**
```json
{
  "match_minute": 45,
  "extra_time": 3,
  "player_name": "John Doe",
  "player_id": 123
}
```

If `player_id` changes, the endpoint automatically adjusts both the old and new player's goal stats.

## Files Changed

| File | Change |
|------|--------|
| `backend/dao/match_event_dao.py` | Added `update_event()` and `get_goal_events()` methods |
| `backend/models/live_match.py` | Added `GoalEventUpdate` model; added `player_id`, `match_minute`, `extra_time` to `MatchEventResponse` |
| `backend/app.py` | Added `GET /api/admin/goals`, `PATCH /api/admin/goals/{event_id}`; fixed player stats bug in `delete_event` |
| `frontend/src/components/admin/AdminGoals.vue` | New component for goals management |
| `frontend/src/components/AdminPanel.vue` | Registered Goals tab |
