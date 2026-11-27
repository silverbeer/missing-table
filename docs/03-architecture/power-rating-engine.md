# Power Rating engine (SB-1805)

The engine behind the MT Power Rating (design: SB-1784). **Slice 1 only**: a pure
library, with no database, API or UI yet. Gathering matches, storing runs and
serving them come in later slices.

| | |
|---|---|
| Code | `backend/mt_tools/power_rating.py`: pure functions and frozen dataclasses, no I/O |
| Tests | `backend/tests/unit/test_power_rating.py`: hand-computed cases plus a regression on the 2026-11-26b backtest freeze |
| Params | `PARAMS_VERSION = "elo-v1"`. Every parameter is a named module constant |

## Model

```
E     = 1 / (1 + 10^(-(R_team - R_opp + H) / 400))    H = +50 home, -50 away, 0 neutral
S     = 1 win · 0.5 draw (shoot-outs are draws) · 0 loss
new R = R + K × G × (S − E)
K     = 30 in every competition; 60 for a team's first 8 rated matches
G     = 1 for a draw or 1-goal margin · 1.5 for 2 goals · 1.75 for 3+ (cap)
start = 1500, or carry_over(): 1500 + 0.3 × (last final − 1500)
```

- **Neutral venue.** Home advantage is 0 when `neutral` is set or the competition
  is `tournament` or `cup`.
- **Not rated.** Forfeits (no football was played), and matches where either
  side is out of pool (no Homegrown conference at this age group). Both are
  counted in `matches_excluded` under `forfeit` and `out_of_pool_opponent`.
  Every key is present, and 0 when nothing was excluded.
- **Order.** `match_date`, then `kickoff_time` (untimed matches go after the timed
  ones that day), then `match_id`. Input order never matters, and every run
  replays the season from the start.
- **Absent, not zero.** A team with no rated match is not in `teams`. It is never
  shown as a 1500 with 0 matches. Empty input gives an empty result.

## API

| Name | What it does |
|---|---|
| `RatedMatch` | Input: one completed match at the age group. Fields: id, date, teams, regulation scores, `competition` (`league`/`flex`/`tournament`/`cup`), `neutral`, `forfeit`, `home_in_pool`/`away_in_pool`, `kickoff_time`, `conference` (the Homegrown division of a League match), penalty scores (carried, never rated) |
| `rate(matches, starting_ratings=None)` → `PowerRatingResult` | Replays the season. Returns `teams`, `deltas`, `matches_counted`, `matches_excluded` and `publication` |
| `TeamRating` | `rating`, `start_rating`, `mp`, `w`/`d`/`l`, `xconf_mp`, `sos` (mean opponent rating before each match), `island`, `conference`, `ranked` (6+ matches), `provisional` (<8), `low_cross_conference` (<3), `tier` |
| `MatchDelta` | Two per rated match: `rating_before`, `opponent_before`, `expected`, `result`, `k`, `margin_mult`, `delta`. This is the source for "the results that moved it most" |
| `Publication` | `national`, `reason` (why not), `main_island`, `main_island_share`, `cross_conference` (each main-island conference → its matches against other conferences) |
| `massey(matches, cap=4, ridge=1.0)` → `MasseyResult \| None` | The nightly audit: capped-margin least squares with a home term (zero on neutral matches) and a ridge on team strengths. Rates the same matches as Elo |
| `rank_gaps(result, audit, threshold=30)` | Ranked teams whose Elo and Massey places within their island differ by more than 30 |
| `carry_over(final, carry=0.3)` | Next season's starting ratings. Carried teams keep the provisional K |
| `tier_for`, `islands`, `team_conferences`, `select_rated`, `match_order`, `expected_score`, `margin_multiplier`, `publication` | The pure pieces, exported for tests and later slices |

A team's conference is the one it played most League matches in, with ties going
alphabetically. It reuses `leaderboards.conference_of`, so the two features
always agree. A match is cross-conference when both teams have a conference and
the conferences differ.

## Publication rule

An age group gets a **national** list only when both of these hold:

1. One island (teams connected by rated matches) holds at least 90% of ranked teams.
2. Every conference in that island has at least 5 matches against other conferences.

Otherwise it gets conference lists only. Only teams that are ranked and in the
main island of a national age group carry a `tier`:

| Tier | Rating |
|---|---|
| `elite` | 1700+ |
| `contender` | 1600–1699 |
| `above_average` | 1500–1599 |
| *(none)* | below 1500 |

## Reproducing the backtest

`test_reproduces_elo_backtest_recommended_config` replays
`~/.local/share/mt-ranking-backtest/2026-11-26b/results_2026-11-26b.csv` and
matches `elo_backtest.py`'s recommended configuration exactly. It is skipped
with a reason when the freeze is not on the machine:

| Check | Engine = backtest |
|---|---|
| Split test (rate to Oct 31, predict decided Nov) | 621/845 (73.5%); U15 137/183, U16 162/217, U17 165/223, U19 157/222 |
| Walk-forward expected-score Brier, Oct / Nov | 0.1678 / 0.1513 |
| Walk-forward Nov accuracy, decided | 73.4% of 845 |
| Ranked teams and rating range at the freeze | U15 129, 1223–1766 · U16 146, 1203–1778 · U17 148, 1198–1754 · U19 147, 1180–1759 |
| Production pool rule | 96 matches excluded; islands U15 [21, 20, 17, 16, 14, 14, 13, 9], U16 [107, 40], U17 [147], U19 [146]; national at U17/U19 only |
