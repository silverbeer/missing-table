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
| Web | **Ranking** tab → Leaderboards (SB-1785) — see [Ranking tab](#ranking-tab) |

## Boards

Top `limit` (default 20, max 50) by rank; ties share a rank (1, 1, 3), so a tie
at the cut is kept.

| key | board | better |
|---|---|---|
| `pts` / `ppg` | Points (W=3, D=1; shootouts count as draws) / points per match | higher |
| `gf` / `gf_pg` | Goals for / per match | higher |
| `ga` / `ga_pg` | Goals against / per match | **lower** |
| `gd` / `gd_pg` | Goal difference / per match | higher |
| `unbeaten` | No losses and at least `MIN_GP` matches, by matches played | higher |
| `pro_wins` | Wins over pro academies (`clubs.pro_academy`), with matches played against them. Pro academies themselves are left off (SB-1819) | higher |

- **`MIN_GP = 6`, on every board.** Totals, per-match boards, `unbeaten` and
  `pro_wins` rank only teams with six matches, so a team with one match and none
  conceded can never top fewest goals against.
- **Unranked teams are listed once**, in the result's `unranked` (rank and value
  null, most matches first, at most `limit`) with the full `unranked_count`. Each
  board carries only its own `unranked_count`. Early in a season that is most
  teams, and listing them on all ten boards flooded MT AI's context and the CLI.
- Each board's `ranked_count` is every team it ranks, not just the `limit`
  shown: the "of N" behind a rank (SB-1782).
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

Every row carries GP, W-D-L, the team's `club_id` and `club_logo_url` (null
when the team has no club or the club no logo; SB-1785, so a client needs no
team or club lookup to draw a logo) and the team's Homegrown conference: the League
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

## Ranking tab

The web UI (SB-1785) is a top-level **Ranking** tab, signed-in only, after
Tournaments. Leaderboards is its first view; Power Rating will join it as a
second sub-tab, and the sub-nav stays hidden until then. No `/ranking` deep link.

| File | Role |
|---|---|
| `frontend/src/components/ranking/RankingView.vue` | Tab shell, sub-tabs |
| `frontend/src/components/ranking/LeaderboardsPanel.vue` | Filters (U15/U16/U17/U19, Homegrown), fetch, loading / empty / error states |
| `frontend/src/components/ranking/LeaderboardCard.vue` | One board: coverage, rows |
| `frontend/src/components/ranking/UnrankedList.vue` | Teams under `min_gp`, once, below the boards |

- Calls `GET /api/leaderboards?league=&age_group=&limit=20` with no season (the
  current one). A filter change refetches; an older answer that lands late is
  dropped.
- Shows the per-game and record boards only, in this order: `ppg`, `gf_pg`,
  `ga_pg`, `gd_pg`, `unbeaten`, `pro_wins`. Totals stay in the API and CLI.
- **Every card leads with `coverage.note` verbatim**, under a one-line
  denominator: "84 U15 Homegrown teams · 8 conferences · min 6 GP".
- Ranks are the API's; a shared rank shows as `T1`. Per-game values to two
  places, `gd_pg` signed, `unbeaten` as W-D-L, `pro_wins` as "2 of 3". A
  missing value is "—", and a board with no rows says "No team qualifies yet",
  never zeros. `no_conference` rows carry a "No Homegrown conference" badge.
- `reason`, or no rows anywhere, is "No results yet" plus the reason; a failed
  read shows the API's message and Retry (which also reloads the league list
  if that failed too).
- Logos come from each row's `club_logo_url`; a team without one shows its
  name alone.
- A team click emits the same `navigate-to-team` payload shape as the Table:
  team, `club_id`, age group and season from the response, league id from the
  (cached) `/api/leagues` list. `divisionId` is null — Matches ignores it when
  a team is selected (SB-1116).
- Below `sm` a board picker shows one card at a time; wider, the cards are a
  grid (two columns, three at `xl`).

## Wording

Soccer plays **matches**, never games. Every user-facing string (board titles,
the coverage note, the web cards, `mt leaders`, dossier and MOTW facts) says
"match", "per match" and "MP" (matches played). The API keeps its field names
(`gp`, `min_gp`, variant `per_game`) so clients don't break (SB-1795).
