# Team dossier (SB-1780)

A scouting summary for one team at one age group, this season: where it stands
**inside its own conferences**. Built for the Match of the Day agent and Fest
match previews, where the two teams usually come from different conferences.
Two conferences share no table, so the dossier describes each team in its own
tables and **never compares across them**: every position, percentile and "top
third" is measured in one table, and every fact names only that table.

| Surface | Call |
|---|---|
| API | `GET /api/teams/{team_id}/dossier?age_group_id=&for_match_id=` — logged-in users only (MT is invite-only) |
| mt-mcp | `get_team_dossier` (read tier) |
| CLI | `mt team dossier TEAM --age U15 [--match ID] [--json]` |
| Code | `backend/mt_tools/team_dossier.py` — pure fact helpers, plus `get_team_dossier(deps, team_id, age_group_id, *, for_match_id, viewer)` |

Give `age_group_id`, or `for_match_id` to take the age from that match. Neither
is 400.

## Conferences

One line per registration (`team_mappings` row) at the age group, kept separate:
`kind` is `league` (a Homegrown or Academy conference), `flex` or `pathway` (Pro
Player Pathway), from `qualification_rules.conference_kind`. A registration in
any other league is not a table the dossier can place a team in, and is skipped
(for the team's lines and for opponents).

- Position of N, W-D-L, GF/GA/GD come from `MatchDAO.get_standings` — the same
  table `/api/table` shows — never a re-tally of results.
- `ppg`, `gf_per_game`, `ga_per_game`, `clean_sheets` (from the team's own
  matches in that table).
- `strength_percentile` (0-100) is `team_strengths` from the Match of the Week
  scorer: points and goal difference per game, as a percentile inside that
  table, damped towards 50 under 3 games (`low_sample`).
- A registered team with no counted result there keeps its line with null
  position and stats and `no_results: true`. Absent is never 0.

`totals` counts the team's played League/Flex matches at the age (counts only:
a rate across two conferences would compare them). Null when there are none.

## Key wins

Played wins at the age, in any competition, over:

| kind | |
|---|---|
| `top_third` | an opponent in the top third of its **own** table: position <= ceil(N/3), N >= 3 |
| `pro_academy_upset` | a pro academy (`clubs.pro_academy`), by a club that is not one |
| `pro_academy` | a pro academy, by another pro academy |

The opponent's table is, in order: the division the match counted in, if the
opponent is registered there; else its registration in the match's competition
(League or Flex); else its first registration, League before Pro Player Pathway
before Flex. Opponent tables are loaded lazily, cached, and capped at
`MAX_OPPONENT_TABLES` (10) distinct tables beyond the team's own;
`coverage.opponent_tables_skipped` counts the distinct tables not loaded. Sorted
strongest opponent first (its strength in its own table), then newest.

**Forfeits are never key wins.** They still count in records and form, where a
`FormEntry` carries `forfeit: true`.

## Form and streaks

The last 5 played League/Flex results at the age, newest first, with opponent
and score (the team's goals first). Friendlies and tournaments are not form. The
streak is `streak_text` from the Match of the Week scorer (3+ wins, unbeaten,
losses), over the whole season.

## Playing up

With `for_match_id`, the match must be in the current season (else 400), and
the bracket age is the match's. A recorded side age (`home_age_group_id` /
`away_age_group_id`) is the team's age: younger than the bracket (by the number
in the name) is playing up; older is `playing_down`, and no playing-up claim is
made. Scraped tournament matches never record side ages, so a team with no
registration at the bracket age and **exactly one** registration at a lower age
is inferred to be playing up from it (`playing_up_inferred`). Two lower ages is
not guessed.

An `age_group_id` given with the match only picks the tables. It must agree with
a recorded side age (else 400); where nothing is recorded, playing up derived
from it is `playing_up_inferred`. The dossier describes the team at its season
age, which is where its tables are. `context` carries `match_id`,
`bracket_age_group`, `season_age_group`, `playing_up`, `playing_up_inferred`,
`playing_down`.

## Facts

Every line is a fact with a stable id the agent must cite:

- `t<team>:a<age>:<kind>:<division_id>:pos|rate|strength|clean_sheets|no_results`
- `t<team>:a<age>:win:<match_id>`
- `t<team>:a<age>:form:last<N>` and `t<team>:a<age>:form:streak`
- `t<team>:a<age>:context:m<match_id>:playing_up` (only when playing up)

Ids do not depend on `for_match_id`, so the same fact has the same id in a
preview and in a plain dossier. Fact text names at most one conference.

## Flags and coverage

Flags: `no_results`, `low_sample` (fewer than 3 League/Flex games),
`no_conference` (no registration at the age), `playing_up`,
`playing_up_inferred`, `playing_down`. `coverage` gives `results_counted`, `tables_loaded`,
`opponent_tables_skipped`, `source` (scraper / user / mixed) and a note that
conferences are never compared.

## Errors

A team with no results is **200** with nulls. An unknown team (or a test team,
for a real viewer), unknown age group, unknown match, a match from another
season, a match the team is not in, an age that contradicts the match's
recorded side age, or neither an age nor a match is 400 (`invalid_args`). A
failed read — the match lookup included (`get_match_by_id(raise_on_error=True)`)
— is 503 with a generic message.
