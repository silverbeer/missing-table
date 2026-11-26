# Leaderboards (SB-1781)

Cross-conference stat boards for one league and age group, over the season's
League and Flex results. **A stat board, not a ranking.** Homegrown conferences
only meet at tournaments, so a team's points and goals are earned against its
own conference and its Flex bracket: the boards compare numbers across
conferences, they do not say who is stronger. Every response says so in
`coverage.note`.

| Surface | Call |
|---|---|
| API | `GET /api/leaderboards?age_group=U15&league=Homegrown&season=&limit=20` — logged-in users only (MT is invite-only) |
| mt-mcp | `get_leaderboards` (read tier) |
| CLI | `mt leaders U15 -l Homegrown [--season 2025-2026] [-n 10] [--board ppg] [--json]` — coverage first, then boards, then the unranked list once (dim) |
| Code | `backend/mt_tools/leaderboards.py` — pure counting and ranking, plus `get_leaderboards(deps, ...)` |

## Boards

Top `limit` (default 20, max 50) by rank; ties share a rank (1, 1, 3), so a tie
at the cut is kept.

| key | board | better |
|---|---|---|
| `pts` / `ppg` | Points (W=3, D=1; shootouts count as draws) / points per game | higher |
| `gf` / `gf_pg` | Goals for / per game | higher |
| `ga` / `ga_pg` | Goals against / per game | **lower** |
| `gd` / `gd_pg` | Goal difference / per game | higher |
| `unbeaten` | No losses and at least `MIN_GP` games, by games played | higher |
| `pro_wins` | Wins over pro academies (`clubs.pro_academy`), with games played against them | higher |

- **`MIN_GP = 6`, on every board.** Totals, per-game boards, `unbeaten` and
  `pro_wins` rank only teams with six games, so a team with one game and none
  conceded can never top fewest goals against.
- **Unranked teams are listed once**, in the result's `unranked` (rank and value
  null, most games first, at most `limit`) with the full `unranked_count`. Each
  board carries only its own `unranked_count`. Early in a season that is most
  teams, and listing them on all ten boards flooded MT AI's context and the CLI.
- Per-game values are compared exactly (fractions), so 2/3 and 4/6 tie; the
  `value` shown is rounded to two places.
- A team that never played a pro academy is **absent** from `pro_wins` and is
  not in its `unranked_count`; it is not 0 wins.

## Counted

- Status `completed` or `forfeit`; a match with no score is skipped and counted
  in `coverage.matches_without_score`.
- `league` must be a top-level league (Homegrown, Academy); a child league such
  as Flex is 400, since it has no conferences of its own. Its divisions and its
  child leagues' are read (`parent_league_id`: Homegrown → Flex).
- Match types are the ones those leagues declare in `leagues.match_type_id`
  (League for Homegrown, Flex for Flex), resolved per call, never hardcoded ids.
- The season defaults to the current one. `get_current_season` returns None on a
  failed read as well as when nothing is flagged, so the fallback is the season
  whose dates contain today, never the newest row (which may not have started);
  with neither, the answer is 503.
- A match is read when it or either side is at the age group, and a side counts
  only at the age group it fielded (`effective_side_age_groups`): a U15 side that
  played up into a U16 match counts at U15 for itself and not at all for its
  opponent. Sides at another age are counted in `coverage.sides_other_age_group`.
- **A level score is a draw, whoever won a Flex shootout.** Flex standings award
  shootout points (`match_types.shootout_points`); these boards do not. The points
  board title and the coverage note say so, so the two totals can disagree.
- Test teams never appear; guest teams (SB-1598) are not filtered and appear like
  any other team.

The read is `MatchDAO.get_season_results`: filtered in the database through a
`divisions!inner` embed and paged with `.range()`, because a league-wide season
is more than PostgREST's 1000-row cap. Paging stops on an empty page, not a short
one, so a server with a lower `max_rows` cannot truncate it silently.

## Conference

Every row carries GP, W-D-L and the team's Homegrown conference: the League
division it played most League games in (ties alphabetical). A team with Flex
games but no Homegrown League games has none: it is shown with
`no_conference: true`, never dropped, and counted in
`coverage.teams_without_conference`.

## Coverage

Every response carries `coverage`: teams, matches, conferences, `min_gp`,
`competitions_present` / `competitions_absent` (U13 and U14 have no Flex, and
the note says "No Flex results at U13."), and the note. An age group with
nothing played is **200** with every board's `rows: []`, `unranked: []` and a
`reason`. An unknown or child league, an unknown age group or season is 400
(`invalid_args`); a failed read is 503 with a generic message.
