# Live Scoring — Offline Sync & Assists (Android app support)

Backend contract added for the native Android live-scoring app (offline-first).
All fields below are **optional**, so the Vue PWA keeps working unchanged.

## Idempotency (`client_event_id`)

Every mutating live/post-match event call accepts a client-generated UUIDv4
`client_event_id`. A partial unique index on `match_events.client_event_id`
is the server-side gate:

1. The event row is inserted **first**, carrying `client_event_id`.
2. If an event with that ID already exists, the request is a **replay** —
   the server returns 200 with current state and performs **no side effects**
   (no score increment, no stats increment, no notification).
3. Score/stats updates run only after a fresh insert.

This makes offline sync exactly-once: a client that lost the response can
safely retry the same request.

Clock actions (`POST /live/clock`) are naturally idempotent instead: an action
whose timestamp column is already set (e.g. `start_first_half` when
`kickoff_time` exists) is a no-op returning current live state.

## Offline time correctness

- `GoalEvent`, `LiveCardEvent`, `LiveSubstitutionEvent` accept optional
  `match_minute` + `extra_time`. If present they are stored verbatim; otherwise
  the server derives the minute from the match clock (`calculate_match_minute`).
- `LiveMatchClock` accepts optional `occurred_at` (must be within the last 3
  hours and not in the future) so a kickoff synced late records the real time.

## Assists

- `POST /api/matches/{id}/live/goal` and `POST .../post-match/goal` accept
  `assist_player_id` (roster player, same team, not the scorer).
- Stored on the goal event (`assist_player_id`, denormalized
  `assist_player_name`) — not a separate event type.
- `player_match_stats.assists` is incremented on create, decremented on goal
  delete, and adjusted on `PATCH /api/admin/goals/{event_id}` scorer/assister
  corrections.

## Live substitutions

`POST /api/matches/{match_id}/live/substitution`

```json
{
  "team_id": 1,
  "player_in_id": 12,
  "player_out_id": 13,
  "match_minute": 55,        // optional
  "extra_time": 2,           // optional
  "client_event_id": "uuid"  // optional
}
```

Creates a `substitution` match event (`player_id` = on, `player_out_id` = off).
Auth: `require_match_management_permission` + `can_edit_match`, same as goals.

## Migration

`supabase/migrations/20260719000000_android_live_scoring.sql` — adds
`assist_player_id`, `assist_player_name`, `client_event_id` to `match_events`
plus the partial unique index `uq_match_events_client_event_id`.

## Tests

`backend/tests/unit/test_live_scoring_idempotency.py` — replay/race behavior,
assist validation and stats, live subs, clock no-op and `occurred_at` window.
