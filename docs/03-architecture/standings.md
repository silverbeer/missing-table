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

## How the combined table is built

The obvious implementation does not work: `filter_same_division_matches` drops
a team's Flex matches from its Homegrown table, because those matches carry the
**Flex bracket's** `division_id`. The same is true one layer down — the database
query filters on `division_id`, so a combined view must not pass one, or it
discards exactly the matches it is combining.

So:

1. Fetch the season + age group **without** a division filter.
2. Keep the selected competitions (`filter_by_match_types`).
3. Keep completed matches.
4. **The table is the division's teams** — those appearing in matches where
   *both* sides are in division X (`teams_in_division`). In practice, its
   League matches.
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
  {"id": 1, "name": "League", "counts_for_qualification": true,  "display_order": 1, "matches": 190, "played": 42},
  {"id": 5, "name": "Flex",   "counts_for_qualification": true,  "display_order": 2, "matches": 68,  "played": 6}
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

## Caching

`get_standings` is cached under `matches:standings:{season}:{age_group}:{division}:{match_type}:{include_test}`
and `get_competitions_present` under `matches:competitions:…`. Both fall under
`mt:dao:matches:*`, which every match write already invalidates, so no new
invalidation is needed.

`include_test` is part of the key on purpose: a test match must not move a real
team's points, so the two audiences never share a computed table (SB-591).
