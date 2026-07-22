# Current Season

The **current season** is an admin-set flag, not a date calculation.

## Why

"Current season" used to be derived from `start_date <= today <= end_date` in
three separate places. In the off-season gap (e.g. a July date between two
seasons) that returns nothing, and season dropdowns silently fell back to a
hardcoded season name (`'2025-2026'`), which breaks every time a new season
starts. An explicit flag removes both problems.

## Model

- `seasons.is_current boolean` — **exactly one** season is current, enforced
  by the partial unique index `seasons_single_current` (unique over the TRUE
  value only).
- Setting a season current clears the flag from all others in one operation
  (`season_dao.set_current_season`).

## Admin UI

**Admin → League Setup → Seasons**:
- A **Current** badge marks the current season.
- **Set current** button on every other row promotes it (clears the old one).
- The Add/Edit season form has a **Set as current season** checkbox.

## Backend

- `season_dao.get_current_season()` / `get_current_season_id()` — prefer the
  `is_current` flag, falling back to the date-spanning season for legacy data.
- `PUT /api/seasons/{id}/current` (admin) — set the current season.
- `POST/PUT /api/seasons` accept `is_current`.
- The three former date-based resolvers (`season_dao`, `invite_service`,
  `player_dao._get_roster_only_players`) all consult the flag first.

## Frontend

Every season dropdown defaults to the current season but stays switchable.
Each component that renders a season `<select>` defaults its selection to
`seasons.find(s => s.is_current)` (falling back to the newest season):
`LeagueTable`, `MatchesView`, `GoalsLeaderboard`, `AdminTeams` (→
`RosterManager` via prop), `TournamentMatchCenter`, and `MatchForm`
(over active seasons).
