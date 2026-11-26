# MT Power Rating — design (SB-1784)

**Status:** Draft, 2026-11-26. Not built. Decisions marked **[owner]** are open.
**Related:** SB-1781 leaderboards (a stat board, not a ranking), SB-1785 Ranking tab
(where this will appear), SB-1786/1787 (data fixes this depends on), SB-1779 audit.

## Goal

A Top N per league + age group (e.g. Homegrown U15) that orders teams **across
conferences**, with a stated confidence, so MT can say more than "led its conference".

### Scope (owner, 2026-11-26)

- **Homegrown, U15 and up** first. Academy and U13/U14 later.
- Every statistic **per match**: teams have played different numbers of games.
- Teams under a **minimum games played** are not ranked (prototype: 6).
- **QoP (mlssoccer Quality of Play) is out.** It exists only at U13 and U14.

## Why results alone are not enough

Measured in prod, 2026-11-26, season 2026-27, Homegrown + Flex results:

| Age | Teams | Conferences | Games between conferences | Connected? |
|-----|------:|------------:|--------------------------:|-----------|
| U15 | 134 | 8 | 0 | no — 8 islands |
| U16 | 149 | 12 | 156 | two islands (9 + 3 conferences) |
| U17 | 149 | 12 | 163 | yes |
| U19 | 148 | 12 | 153 | yes |

Homegrown conferences only meet at tournaments such as MLS NEXT Fest. At U16+ the
links are Pro Player Pathway teams playing Flex against nearby regional conferences,
not conferences meeting each other. **A rating can only order teams that are linked
by games.** Two teams in separate islands have no comparison at all, whatever the
model.

## Inputs

| Input | Use | Status |
|-------|-----|--------|
| Season League + Flex results | within-conference strength | in MT; Flex backfilled 2026-11-26 (SB-1786), scores reconciled by SB-1787 |
| MLS NEXT Fest 2026 results (Dec 2–13) | the cross-conference links | needs Fest ingest (SB-1745..1748) |
| Same birth-year cohort, 2025-26 (incl. Fest 2025) | a starting point (prior) | in MT; cohort = U15 now ↔ U14 then |
| Playoffs, Cup | more links later in the season | later |

## Candidate models

Comparison of the approaches the owner is researching (NCAA men's soccer and other
sports' systems). **[owner]** fill in from that research — keep each to what the
method needs from our data and what it gets wrong.

| Model | Needs | Strength | Weakness |
|-------|-------|----------|----------|
| Points / goal difference per game | results only | simple, explainable | ignores who you played |
| Least-squares rating on capped goal margin (Massey-style) | results; connected graph | uses margin and opponent; prototype built | islands are incomparable; margin can reward running up scores (cap mitigates) |
| Elo-style, updated game by game | results in date order | handles time / form | order-dependent; needs tuning per age |
| Bayesian rating (e.g. Poisson goals model) | results; priors | gives honest uncertainty; prior from last season | more to explain |
| _[owner: NCAA RPI-style / other researched systems]_ | | | |

### Prototype (2026-11-26)

`ratings.py` (attached to SB-1784; local copy
`~/.local/share/mt-ranking-backtest/2026-11-26/`): least-squares on goal margin capped
at ±4, fitted home advantage (0.25–0.37 goals by age), ridge 1.0 toward 0, standard
error per team.

In-season check — rated on results to Oct 31, predicted the winner of 845 decisive
November games (176 draws excluded):

| Model | All | U15 | U16 | U17 | U19 |
|-------|----:|----:|----:|----:|----:|
| Home team wins (baseline) | 57.8% | | | | |
| Points per game | 70.2% | 68.1% | 73.1% | 72.3% | 67.0% |
| Goal difference per game | 71.7% | 68.4% | 75.1% | 72.5% | 70.1% |
| Capped-margin rating | 72.9% | 69.9% | 74.2% | 76.2% | 70.7% |

Almost all of those games are inside one conference, where every method does well.
Fest is the real test. Standard errors of ±0.55–0.75 goals mean neighbouring ranks
overlap heavily.

> The prototype ran before SB-1786 added 120 missing Flex results. Re-freeze before
> Fest (see Validation).

## Decisions the design must make

1. **Model.** Pick from the table above using the Fest backtest, not intuition.
2. **Islands.** A component with no links to the rest is ranked inside itself only,
   never merged into one national order. The UI says which island a team is in.
3. **Confidence.** Each team carries an uncertainty; publish **tiers / bands**, not
   strict 1..20 positions, when intervals overlap.
4. **Unranked.** Below the minimum games, or in an island too small, the team is
   "unranked — too few links", never placed.
5. **Fest weighting.** Neutral site (no home advantage). Showcase matches have no
   stakes but are still real results; knockout and group games count the same.
6. **Cohort carry-over.** How much last season's same-birth-year rating counts, and
   how fast it decays as this season's games arrive.
7. **Margin cap / blowouts.** Cap value; whether a forfeit counts (proposal: no).
8. **Per-age availability.** U17/U19 now (connected), U16 after Fest, U15 only once
   Fest links its 8 islands.
9. **Wording.** "MT Power Rating, from N teams in MT" — never "Top 20 in MLS NEXT".
   Coverage on every board (CLAUDE.md aggregate rule).

## Validation (required before publishing)

1. **Re-freeze** season results on 2026-12-01, after SB-1786 (done) and SB-1787
   (reconcile) — before Fest's first game on Dec 2.
2. Predict every Fest match at U15+ from the frozen ratings. Cross-island U15
   predictions fall back to per-game stats / last-season prior, and are scored
   separately.
3. Score hit rate (decisive games) and Brier score against Fest results, per age and
   per model, vs the baselines above.
4. **The measured result decides** whether, and at which ages, the rating ships.
   `ratings.py score <dir> fest_results.csv` already does the hit-rate part.

## Where it shows

- Ranking tab (SB-1785) → a "Power Rating" sub-tab next to Leaderboards.
- MOTD agent facts (SB-1561): "rated 3rd of 149 U17 teams in MT (band 2–6)".
- Scouting tab (SB-1782) badges; `mt` CLI; mt-mcp tool.

## Build tickets (to file once the model is chosen)

- Rating engine (pure functions + nightly job writing a ratings table).
- Fest backtest harness (frozen inputs, scoring report).
- API + mt-mcp tool + Ranking sub-tab.
