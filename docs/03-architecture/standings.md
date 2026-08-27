# Standings

`GET /api/table` serves three different questions, and only one of them
produces a league table.

| `match_type` | Question | Is it a standing? |
|---|---|---|
| a competition name (`League`, `Flex`, `Tournament`, …) | how does this competition stand | **yes** |
| `qualifying` | what is this team's record across the competitions that qualify it for the cup | no — a record |
| `all` | what is this team's record across everything, friendlies included | no — rarely what anyone wants |

## Why `qualifying` is not just "League + Flex"

It is the union of every match type flagged `match_types.counts_for_qualification`
(SB-849). Nothing in the standings code, the Matches tab or the CLI names the
competitions, so a new qualifying competition is one `UPDATE` on one row and
every surface agrees. Three bugs in two days came from the opposite shape — a
rule spelled out separately in the frontend, the CLI and the ingest path, and
updated in one of them.

`mt team matches -c qualifying` and the Matches tab's Qualifying chip read the
same flag. If they ever disagree with the table, one of them stopped reading it.

## Why a combined view is not a standing

MLS NEXT Flex brackets cut across Homegrown divisions. 31 of 52 brackets still
mix regions after folding Pathway into its parent, and 580 Flex fixtures are
cross-region. So in a Northeast U15 qualifying table, a team's points include
matches against opponents **who are not in that table**.

That is a record of what a team has done, not a competition in which everyone
has played everyone. Per CLAUDE.md, *any cross-team statistic ships with its
coverage or it does not ship* — so the response carries one:

```json
{
  "standings": [ ... ],
  "coverage": {
    "match_type": "qualifying",
    "competitions": ["Flex", "League"],
    "matches_counted": 250,
    "matches_vs_outside_table": 31,
    "teams_outside_table": 12
  }
}
```

A client rendering `qualifying` or `all` with a non-zero
`matches_vs_outside_table` and no caption is presenting a record as a standing.
`competitions` is `null` for `all` — every competition, not a list.

## What "in this division" means

**A match belongs to the division its own `division_id` names.** One rule, used
everywhere.

That was not always so, and the old rule was wrong twice (SB-835). It asked
whether *both teams* carried the division as their `teams.division_id`:

- **Flex tables were always empty.** A Flex bracket's participants are Homegrown
  teams, every one of them carrying a Homegrown `division_id`. The teams test
  kept 0 of 68 Flex matches, so picking Flex in the league table produced a
  blank screen in production.
- **A team row holds one division for every age group.** A club playing U14 in
  New England and U15 in Northeast has a single `teams.division_id`. That
  dropped 88 New England U14 League matches from the 2025-2026 table. It is
  also a *current* value applied to *historical* matches, so a team changing
  division silently rewrites old seasons.

Fixing it moved 2025-2026 League from 1177 counted matches to 1265, and left
2026-2027 Northeast League at 190 — unchanged, because there every match's
teams were already recorded under the division they played in.

## How the combined table is built

The obvious implementation still does not work: a team's Flex matches carry the
**Flex bracket's** `division_id`, so filtering a Homegrown table by division
drops them. That applies one layer down too — the database query filters on
`division_id`, so a combined view must not pass one, or it discards exactly the
matches it is combining.

So:

1. Fetch the season + age group **without** a division filter.
2. Keep the selected competitions (`filter_by_match_types`).
3. Keep completed matches.
4. **The table is the division's teams** — those appearing in matches filed to
   division X (`teams_in_division`). In practice, its League matches.
5. **The matches counted are those teams' matches in any selected competition**
   (`filter_matches_involving`), including ones where the opponent is outside.
6. Standings are calculated with `only_team_ids` set to that roster, so an
   outside opponent's result counts for the team in the table and does not earn
   the outsider a row of its own.

A single competition skips all of this: the division filter runs in the query
as before, and `matches_vs_outside_table` is 0 by construction.

## Which competitions exist here

```
GET /api/match-types/available?season_id=&age_group_id=&division_id=
```

```json
[
  {"id": 1, "name": "League", "counts_for_qualification": true, "display_order": 1, "matches": 190, "played": 42, "in_division": 190},
  {"id": 5, "name": "Flex",   "counts_for_qualification": true, "display_order": 2, "matches": 68,  "played": 6,  "in_division": 0}
]
```

U13 and U14 play no Flex; U13/U14/U15 have no Pro Player Pathway divisions. A
client must ask rather than hardcode age-group ids, which rot the first time
MLS Next moves the boundary — and a competition tab that always yields an empty
table is the loading skeleton CLAUDE.md warns about.

Two things to note:

- With `division_id`, the answer is scoped to that division's **teams**, not to
  matches carrying its `division_id`. A Homegrown team's Flex matches sit under
  a Flex bracket id, and they are precisely what a Flex tab would show.
- `matches` and `played` are both returned because *"no results yet"* and
  *"not played here"* are different answers, and only one of them means the tab
  should be hidden.
- `in_division` counts how many of those matches actually carry this
  `division_id`, which identifies the division's **own** competition — League
  for Northeast, Flex for Turnpike. That is what a standings screen should open
  on, and reading it here is what keeps a league-name → competition map out of
  the frontend.

## Which leagues are worth offering

```
GET /api/leagues/available?season_id=
```

A league is offered when it is **active**, or when the selected season actually
has matches in it. Both halves are load-bearing (SB-851):

- **Presence alone empties a filter before a season starts.** Only U15 is
  loaded for 2026-2027, so presence would drop Academy — and with it three
  legitimate IFA teams — from a club's team picker.
- **`is_active` alone hides real history.** Kick Futsal is inactive and its 24
  matches are all 2025-2026; hiding it outright makes that season unreachable
  through the filter.

So `is_active` is the pre-season safety net, and presence is what re-admits a
dormant league to the seasons it actually played. Each row carries
`matches_this_season`.

Two implementation notes worth keeping:

- **Never key this on `teams.league_id`.** Flex has *zero* teams by that column
  — its participants are Homegrown teams — so any rule using it hides the
  newest competition in the product. Matches resolve to a league through
  `divisions`.
- `get_leagues_present` returns a **list** of `{league_id, matches}`, not a map
  keyed by league id. It is cached, JSON has no integer keys, and a
  `dict[int, int]` comes back from Redis with string keys — every lookup would
  then miss and every league would read as zero matches.

Both `LeagueTable.vue` (the League row) and `MatchesView.vue` (the My Club team
picker) read this list; the picker hides a team whose league is not offered.
A team whose division cannot be identified is kept — missing metadata is not
evidence that a team is defunct, and hiding a real team is the worse error.

## The league table's competition control

`LeagueTable.vue` builds its Competition row from this endpoint. It opens on
the competition with `in_division > 0`, offers a **Qualifying** chip only when
more than one flagged competition is present (with one it would restate the
chip beside it), and hides the control entirely when there is only one.

Changing division re-reads the endpoint and reconciles the selection: a
division that does not play the current competition falls back to its own,
rather than leaving the filter pointed at something with no matches. That is
the shape of the bug this replaced — `/api/table` was called with no
`match_type` at all, so it defaulted to League, and a Flex bracket has none.

Whenever `coverage.matches_vs_outside_table` is non-zero the table renders a
caption saying so. A combined view without one is a record presented as a
standing.

## Caching

`get_standings` is cached under `matches:standings:{season}:{age_group}:{division}:{match_type}:{include_test}`
and `get_competitions_present` under `matches:competitions:…`. Both fall under
`mt:dao:matches:*`, which every match write already invalidates, so no new
invalidation is needed.

`include_test` is part of the key on purpose: a test match must not move a real
team's points, so the two audiences never share a computed table (SB-591).
