# MT Power Rating — design (SB-1784)

**Status:** Design for owner approval, 2026-11-27. Not built. Open decisions are at the end.
**Related:** SB-1781 leaderboards (a stat board, not a ranking), SB-1785 Ranking tab (where this
appears), SB-1803 coming-soon note, SB-1786/1787 (data fixes this depends on).
**Inputs:** the owner's research brief (26 Nov 2026, cited as *brief §n*) and MT's own results. Where
they disagree, MT's measurement wins and the table says so.

## Recommendation

1. **Publish an Elo rating, audit it nightly with capped-margin Massey.** On MT's November results
   every model predicts about 73% of decided matches, and the gaps are inside the noise. Massey's
   probabilities are slightly better (log-loss 0.872 vs 0.885). Elo is close enough, and it can
   answer "why did it move?" one match at a time, which Massey cannot.
2. **Parameters come from MT data.** K = 30 for every competition (doubled for a team's first 8
   matches), goal margin capped at 3, home advantage **+50** (the brief proposed 75; MT's data
   fits 50).
3. **No national list until the teams are connected by matches.** U15 is 8 separate islands today.
   Launch after MLS NEXT Fest (Dec 2–13), and only once the Fest backtest has been scored.

## Scope (owner, fixed)

- **Homegrown U15, U16, U17, U19.** One rating per age group. QoP (U13/U14 only) stays out.
- Teams with fewer than **6 matches** are not ranked. Everything shown is per match.
- Shoot-outs count as **draws**. In anything user-facing it is **matches, never games**.
- Signed-in users only (MT is invite-only). It goes under the **Ranking** tab, next to
  Leaderboards.

## Why results alone cannot give a national order

Measured in prod, season 2026-27, Homegrown League + Flex, frozen 2026-11-26 (3,232 matches):

| Age | Teams | Conferences | Islands (teams) | Teams with 0 / 1–2 / 3+ cross-conference matches |
|-----|------:|------------:|-----------------|-------------------------------------------------:|
| U15 | 134 | 8 | 8 (22, 21, 17, 17, 16, 15, 14, 12) | 124 / 0 / 0 |
| U16 | 149 | 12 | 2 (109, 40) | 23 / 83 / 41 |
| U17 | 149 | 12 | 1 | 26 / 78 / 43 |
| U19 | 148 | 12 | 1 | 25 / 78 / 43 |

At U16 and above, the 12 "conferences" include 4 **Pro Player Pathway** conferences, and every
cross-conference match is a PPP team playing Flex against a regional conference. Regional
conferences never play each other. Each regional conference has only 8–40 such bridge matches.
**A rating can only order teams that matches connect** (brief §6, "the hard limit"). Fest is the
first event where regional conferences meet.

Two corrections to the brief's picture of the league (brief §1):
- **Flex is half the season, not ~6 matches.** The median team has played 11 matches, and Flex is
  50–55% of them. The brief's case for K = 25 on Flex (brief §7, "≈27% of a season's weight")
  rested on Flex being small.
- There are **8 regional conferences plus 4 PPP conferences**, not ~7.

## Backtest on MT data

Script: `elo_backtest.py`, to sit beside `ratings.py` in
`~/.local/share/mt-ranking-backtest/2026-11-26b/`. Run `python -I elo_backtest.py backtest
results_2026-11-26b.csv`. It is deterministic (fixed bootstrap seed). `elo_backtest.py rollover
u14_2025-26_league.txt results_2026-11-26b.csv` runs the rollover test.

**Protocols.**
- **Walk-forward:** every match day is predicted only from earlier days. October predictions fit
  a calibration (ordered logit: home win / draw / away win). November (Nov 1–22) is the test.
- **Split:** the prototype's protocol. Rate on matches up to Oct 31, then predict November with no
  updates.

Every team starts at 1500 on Sep 5. No prior season exists for most conferences (see Rollover).

The backtest used the prototype's match set, which still includes the 96 matches against
out-of-pool opponents that the production rule below excludes (3% of matches).

### Headline: November, 1,021 matches (845 decided)

| Model | Accuracy, decided (95% CI) | Log-loss | Brier (3-way) | Split test |
|-------|---------------------------:|---------:|--------------:|-----------:|
| Home team wins | 57.8% (54.4–61.0) | | | 57.8% |
| Points per match (PPG) | 73.1% (70.0–76.0) | 0.906 | 0.529 | 71.7% |
| Massey, margin cap 4 (prototype) | 73.1% (70.0–76.0) | **0.872** | **0.508** | **75.4%** |
| Elo, brief defaults (K20, Flex×1.25, HFA 75) | 73.1% (70.0–76.0) | 0.888 | 0.517 | 73.5% |
| **Elo, recommended** (K30, cap 3, HFA 50) | 73.4% (70.3–76.2) | 0.885 | 0.516 | 73.5% |

Paired differences against recommended Elo (bootstrap 95% CI):

| vs | Accuracy | Log-loss (positive = Elo better) |
|----|---------:|---------------------------------:|
| PPG | +0.2% [−1.7, +2.2] | **+0.021 [+0.007, +0.034]**, Elo better |
| Massey cap 4 | +0.2% [−1.7, +2.2] | **−0.013 [−0.024, −0.001]**, Massey better |
| Elo, brief defaults | +0.2% [−0.8, +1.3] | +0.002 [−0.001, +0.006], no difference |

**How to read this:**
- **Accuracy cannot separate the models.** 845 decided matches give about ±3 points of CI.
- **Log-loss can.** Elo's probabilities beat PPG's. Massey's beat Elo's, narrowly, and the split
  test agrees (75.4% vs 73.5%, a 16-match gap). Massey fits every match at once. Elo is still
  catching up from a cold start at 1500.
- **Cross-conference matches** (Oct–Nov, n = 283 decided): Massey 74.9%, Elo 74.6%, PPG 69.6%
  (CIs about ±5). This is the only cross-conference evidence before Fest, and here PPG is the
  model that falls behind.
- **This is not the Fest test.** Almost every match here is inside a conference or a Flex bracket.
- The prototype's 72.9% Massey figure (2026-11-26) came from the data before SB-1786 added 120 Flex
  results. On the 26b freeze, the same split gives 75.4%.

### What the parameter grid says

128 Elo configurations: K {15, 20, 25, 30} × Flex {1, 1.25} × cap {3, 4} × HFA {0, 50, 75, 100} ×
provisional {off, on}. Each was tuned on October's expected-score Brier and checked on November.

| Factor | Finding | Decision |
|--------|---------|----------|
| K | Higher is better up to 30–40 (Oct Brier 0.1715 at K20 → 0.1673 at K30 → 0.1668 at K40). Above 50 it gets worse. This is a cold-start effect. | **K = 30** |
| Provisional K×2, first 8 matches | Largest single effect (mean Brier 0.1835 → 0.1731) | **On** |
| Home advantage | Sweep 0–160: minimum at 40–60. Home teams score 0.570 of points, which implies +49. | **+50** (brief: 75) |
| Margin cap 3 vs 4 | No measurable difference (0.1786 vs 0.1780) | **3**: the safeguarding message (brief §7, pitfall 2) at no cost |
| Flex ×1.25 | No measurable difference (0.1775 vs 0.1791), and Flex is half the matches | **×1.0** |

### Rank stability

Place moves within the team's island, ranked teams only, Oct 1–Nov 22, 3,007 team-matches:

| Config | Median | 95th pct | Max | Matches moving a team >15 places |
|--------|-------:|---------:|----:|---------------------------------:|
| Recommended | 2 | 13 | 34 | 3.1% |
| Brief defaults | 2 | 12 | 28 | 2.5% |

Brief pitfall 9 asks for no move above ~15 places on one ordinary match. About 3% of matches break
that. The cause is density, not volatility: rating SD is about 128, so mid-table teams sit 1–3
points apart and a single result passes many of them. The fix is in presentation: show the
rating, group by tier, and report movement in points as well as places. Lowering K would cost
accuracy.

### Elo vs Massey at the freeze

The two orders agree closely (Spearman 0.94–0.96 per age). At U17/U19, the gap between a team's
two ranks is 6–9 places at the median, 23–24 at p90 and 30–34 at p95. The brief's audit rule
(flag any gap above 10 places, brief §7) would flag 52–63 of ~147 teams, which nobody would read.
**Flag gaps above 30 places**, about the worst 5%.

### Season rollover (brief §7 proposes carrying 70%)

MT has a prior season only for Northeast, Florida and Mid-Atlantic. The test: 2025-26 U14 League
results (581 matches, 54 teams) seed 2026-27 U15 ratings, scored on U15 Sep–Oct matches between two
seeded teams (n = 139, 114 decided). Team ids carry across seasons and age groups:

| Carry c (start = 1500 + c·(final − 1500)), provisional K kept | Brier | Accuracy |
|---|---:|---:|
| 0 (start at 1500) | 0.1795 | 66.7% |
| **0.3** | **0.1752** | 67.5% |
| 0.5 | 0.1762 | 67.5% |
| 0.7 (brief) | 0.1796 | 64.9% |
| 1.0 | 0.1875 | 64.9% |

A small carry helps. The brief's 70% is no better than starting fresh, but n is small and all
these differences are within noise. **Recommend 0.3.** Re-test in September 2027, when a full
national season exists.

## The model

```
expected  E = 1 / (1 + 10^(−(R_team − R_opp + H) / 400))     H = +50 at home, −50 away, 0 at tournaments
result    S = 1 win · 0.5 draw (incl. shoot-outs) · 0 loss
new R     R + K × G × (S − E)
K         30 for every competition; 60 during a team's first 8 counted matches
G         1 for a draw or 1-goal win · 1.5 for 2 goals · 1.75 for 3+ goals (cap)
start     1500 (new season: 1500 + 0.3 × (last final − 1500))
```

Points exchange is equal and opposite, except while one side is still on its provisional K.

| Choice | Brief | MT design | Why |
|--------|-------|-----------|-----|
| Core | Elo, one stream per age (§7) | **Adopt** | Explainable per match, handles unequal match counts |
| Scale 400, start 1500 | §7 | **Adopt** | |
| K League / Flex | 20 / 25 | **30 / 30** | Grid above; Flex is half the season |
| K Fest, GA Cup | 30 | **30** (×1.0), re-tuned after Fest | Brief §2 cites Szczecinski & Roatis: importance weights hurt prediction. Brief §7 caps Fest at ~30 |
| K MLS NEXT Cup | 35 | **30** until tested on the June 2027 Cup | No data yet; brief §11 calls 35 a proposal |
| Margin G | 1 / 1.5 / 1.75, cap 3 (§7) | **Adopt** | Cap 3 vs 4 measured equal |
| Home advantage | +75 (§7) | **+50** | Fitted (above) |
| Provisional | K×2, first 8 (§7) | **Adopt** | Largest measured gain |
| Shoot-outs | Draw (§7) | **Adopt** | Owner decision |
| Knock-out protection | None (§8) | **Adopt** | Stays zero-sum |
| In-season decay | None (§7) | **Adopt** | |
| Rollover | 70% carry (§7) | **30% carry** | Measured above |
| Audit | Massey monthly, flag >10 (§7) | **Massey nightly, flag >30** | Cheap to run nightly; >10 flags about 40% of teams |
| Human polls | Never in the number (§6) | **Adopt** | |

## What counts

| Rule | Decision |
|------|----------|
| Competitions | Homegrown League, Flex, and tournament matches (Fest, GA Cup, MLS NEXT Cup) between two in-pool teams |
| Status | `completed` only. **A forfeit is not counted**: no football was played (the leaderboards do count forfeits as results) |
| Score | Regulation `home_score`/`away_score`. A non-null `home_penalty_score` means the match was decided on penalties, and it is rated as a draw. Today 268 of 502 drawn matches went to a shoot-out |
| Venue | League/Flex: the home team gets +50. Any match with `tournament_id` set is neutral (tournament matches have `match_type` Tournament and no division) |
| Pool | A team is **in pool** at an age group if it has a Homegrown conference there this season. That includes the 4 Pro Player Pathway conferences: they are Homegrown members, ranked like anyone else, with a "Pro academy" tag (`clubs.pro_academy`) |
| Out-of-pool opponents | MLS academy sides with no Homegrown conference at that age (10 at U15, 2 at U16+), and international or other clubs at tournaments. **Their matches are excluded** (brief §8). They exchange no points, and are counted in `coverage.matches_excluded`. Cost today: 96 of 3,232 matches. Removing them leaves the islands unchanged, so they connect nothing |
| Play-ups | A match counts only if both sides fielded this age group (`home/away_age_group_id`) |
| Order | By `match_date`, then `kickoff_time`, then `id`. Every run replays the season from its first match, so a late or corrected result is placed in date order, never patched in (brief §7) |

## Publication: islands, badges, tiers

**National list for an age group** only when both of these hold:
1. One island holds at least 90% of ranked teams, and
2. Every conference in that island has at least 5 matches against other conferences.

Otherwise the age group shows **conference lists only**, with no national rank and no tiers.
Conference lists are never interleaved into a national order (brief §6). A team outside the main
island is shown under its own conference, marked *not yet comparable nationally*.

Today: **U15 no** (8 islands), **U16 no** (73% in the largest island), **U17/U19 yes** (the
thinnest conference, Southwest at U17, has 8 bridge matches). Fest should connect all four. The
launch waits for Fest regardless.

| Badge | Rule | Today (U17, 147 in pool) |
|-------|------|------------:|
| *Unranked — 4 of 6 matches* | MP < 6: listed separately, never placed, never shown as 0 | 0 |
| **Provisional** | 6–7 MP (still on K×2) | few; most teams have 11+ |
| **Low cross-conference data** | fewer than 3 matches against other conferences (brief §7) | 104 |
| **Pro academy** | `clubs.pro_academy`, information only | 29 PPP teams |

**Tiers** use fixed cut-offs on the 1500 scale, set from the measured distribution. Every connected
pool has a mean of about 1500 and an SD of about 128, so the cut-offs hold their meaning:

| Tier | Rating | Share today (U16–U19) |
|------|--------|---------------------:|
| Elite | 1700+ | 4–6% (6–9 teams) |
| Contender | 1600–1699 | 17–22% |
| Above average | 1500–1599 | 24–31% |
| *(no label)* | below 1500 | 46–50% |

The brief's "Conference leader" label for 1500–1599 is dropped (brief §7 mock): that band is "above
average", not a conference lead. Tiers appear in the national view only, and their cut-offs are
shown on screen.

## Data model

New migration, three tables. The engine is pure (`backend/mt_tools/power_rating.py`). The tables
only store what it published.

| Table | Rows | Key columns |
|-------|------|-------------|
| `power_rating_runs` | one per (season, age group, league) per run | `id`, `season_id`, `age_group_id`, `league_id`, `computed_at`, `through_date`, `params` jsonb + `params_version` ("elo-v1"), `input_fingerprint` (hash of counted match ids + scores), `matches_counted`, `matches_excluded` jsonb, `national` bool, `publication_reason` |
| `power_ratings` | one per team per run | `run_id` FK cascade, `team_id`, `rating`, `start_rating`, `rank` (null = unranked), `island`, `conference_division_id`, `conference_rank`, `mp`, `w`, `d`, `l`, `xconf_mp`, `sos` (average opponent rating before each match), `tier`, `badges` text[], `massey_rank` |
| `power_rating_match_deltas` | two per counted match, **latest run only** | `run_id`, `match_id`, `team_id`, `opponent_id`, `rating_before`, `opponent_before`, `expected`, `result`, `k`, `margin_mult`, `delta` |

- A correction from the reconcile job (SB-1787) changes the fingerprint, and the next run replays
  the season. **Movement** compares the team with the run published 7 days earlier, which is what
  users actually saw. "Why it moved" is read from the deltas, so a corrected match shows up there.
- A run with an unchanged fingerprint writes nothing.
- **Backup (SB-1071 rule):** `power_rating_runs` and `power_ratings` go in `TABLES_TO_BACKUP`. They
  are the record of what MT published about minors' teams, which cannot be reproduced once the
  parameters change. `power_rating_match_deltas` goes in `EXCLUDED_TABLES`: it is derived and
  rebuilt on every run. No user FKs.
- Size: about 600 rating rows per run, and about 6.5k delta rows (latest only). Negligible.

## Recompute job

**Recommended: a Celery beat task in the backend worker on the k3s cluster, nightly.** Default
10:00 UTC; set it to just after the nightly reconcile once that schedule is fixed. Also add an
admin trigger, `POST /api/admin/power-rating/recompute`, which runs the same engine in-process.

| | Backend Celery beat | match-scraper CronJob |
|---|---|---|
| Owns the data and DAO | yes, same repo as engine and tests | no; would need a new ratings-write API |
| Credentials | worker already writes prod | adds a write path to MT |
| Coupling | analytics stays out of ingest | couples scraping to rating |
| Cost | add `celery beat` (single replica) to `k3s/worker` | a new CronJob |

Caveats:
- **Before SB-1807 no beat ran anywhere.** The k3s prod worker now runs the only one (below).
  `maintenance_tasks.py` still has no schedule entry, and is not imported by `celery_tasks`.
- **The worker cannot clear the API's Redis cache** (`caching.md`). The API therefore caches the
  rankings payload keyed by `run_id`, and reads the latest run id uncached.
- **If the M4 is down, the ratings go stale, not wrong.** The page shows "updated <date>", and the
  admin trigger works from LKE.
- A full replay costs milliseconds: about 1k matches and a 150×150 solve for each age group.

### Built (SB-1807)

| Piece | Where |
|---|---|
| Tables | `supabase/migrations/20261127140000_power_rating_tables.sql`: the three above. RLS on: logged-in users read, only the service role writes |
| Input and storage | `backend/dao/power_rating_dao.py`. `to_rated_matches` (pure) maps rows to `RatedMatch`; `PowerRatingDAO` reads, writes runs, and answers `latest_run` / `latest_run_id` / `run_as_of` (the run users saw at a time, for 7-day movement) |
| Orchestration | `backend/services/power_rating_service.py` `recompute(store, season_id=None, age_groups=("U15","U16","U17","U19"), league="Homegrown")` |
| Nightly | Celery task `power_rating.recompute_all` (`backend/celery_tasks/power_rating_tasks.py`); `BEAT_SCHEDULE` in `backend/celery_app.py`, 10:00 UTC, queue `power_rating` |
| Beat | embedded in the k3s prod worker: `--beat`, `--queues=matches.prod,power_rating` (`k3s/worker/deployment-prod.yaml`, README "Celery beat") |
| Admin trigger | `POST /api/admin/power-rating/recompute?season_id=&age_group=U17&age_group=U19&league=Homegrown`, admin only. Runs `recompute` in-process and returns the summary. Unknown league or age group, or no current season: 400. A failed read: 503 |

**What a run reads.** For each age group: the season's League and Flex fixtures of Homegrown
and its child leagues (the leaderboards' read, `MatchDAO.get_season_results`), and every
tournament match at the age group (`tournament_id` set, no division). League fixtures **in any
status** decide the pool: a team is in pool when it has a Homegrown League fixture at that age
this season, scheduled or played. This matters early in a season: on a 2026-09-20 snapshot,
"has played a League match" left half the U15 Flex teams out of pool. Only `completed` and
`forfeit` matches go to the engine. A match in which either side fielded another age group is
not rated and is counted as `other_age_group`. A completed match with no score is counted as
`no_score`. Tournament matches are all `competition="tournament"` (neutral). The engine does
not yet distinguish `cup`, and both are rated the same.

**What a run writes.** One `power_rating_runs` row (`matches_excluded` holds `forfeit`,
`out_of_pool_opponent`, `other_age_group` and `no_score`, each present, 0 when none), one
`power_ratings` row per rated team, and the deltas. Older runs' deltas for the same season, age
group and league are then deleted. The ranks:
- `rank`: only when the age group is national, ranked teams in the main island, by rating.
- `conference_rank`: ranked teams within their conference, by rating.
- `massey_rank`: ranked teams within their island, by the Massey audit.

An unranked team (under 6 matches) carries none of them. `badges` holds `provisional` (ranked,
under 8 matches) and `low_cross_conference`. `pro_academy` is not a badge here. It is read from
`clubs.pro_academy` when the rankings are served (slice 4).

**Skip when unchanged.** `input_fingerprint` is a sha256 of the whole engine input (match ids,
dates, teams, scores, status, competition, pool flags, conference) plus `PARAMS_VERSION`. When it
equals the latest run's, nothing is written and the summary says `unchanged`. A score
correction, a new forfeit, a team gaining a conference, or a parameter change all produce a new
run. An age group with nothing played still gets one run, with no teams and a reason.

**Not atomic.** PostgREST has no multi-statement transaction. If a ratings or deltas insert
fails, the run row is deleted again (its ratings and deltas cascade) and the error is raised, so
a half-written run never becomes the latest. While a run is being written, for a few hundred
milliseconds, a reader can see it with only some of its ratings.

**One age group failing does not stop the others.** It is reported as `failed` in the summary,
with the detail in the log only.

#### Operator steps

1. `./scripts/db_tools.sh migrate prod`, from the main checkout, **before** the code reaches prod.
   The admin trigger and the nightly task write to the new tables.
2. Merge. The API (LKE) gets the admin trigger with the normal deploy.
3. Build the worker image from the merged main: `./k3s/worker/rebuild-and-deploy.sh --build-only`.
4. The args changed, so the manifest must be applied, and applying resets the image to the
   mutable `:latest` (SB-860). Re-pin straight away:
   `kubectl apply -f k3s/worker/deployment-prod.yaml && ./k3s/worker/rebuild-and-deploy.sh --deploy-only`.
   Then `./k3s/worker/rebuild-and-deploy.sh --check` should report HEAD.
5. Check: `rabbitmqctl list_queues name messages consumers` shows `power_rating` with 1 consumer,
   and the worker log shows `beat: Starting...`.
6. Seed the first runs without waiting for 10:00 UTC: `POST /api/admin/power-rating/recompute` as
   an admin.

**Keep the worker at one replica.** Every pod with `--beat` is a scheduler. To scale out, move
beat to its own single-replica Deployment first.

## API

`GET /api/rankings?age_group=U17&league=Homegrown&season=&view=national|conference&conference=` is
for logged-in users. It shares `mt_tools.power_rating` with the mt-mcp tool `get_power_rating`
(read tier) and with `mt rankings U17`, the same pattern as `/api/leaderboards`.

```json
{
  "league": "Homegrown", "age_group": "U17", "season": "2026-2027",
  "run": {"id": 412, "computed_at": "2026-12-15T10:00:04Z", "through_date": "2026-12-14",
          "matches_counted": 1122, "params_version": "elo-v1"},
  "publication": {"national": true, "reason": null},
  "coverage": {"teams_in_pool": 147, "ranked": 146, "unranked_count": 1,
               "matches_excluded": {"out_of_pool_opponent": 13, "forfeit": 0, "other_age_group": 0},
               "note": "MT Power Rating from 147 Homegrown U17 teams in MT. Conferences meet only at Flex and national events."},
  "tiers": [{"key": "elite", "label": "Elite", "min": 1700}, {"key": "contender", "label": "Contender", "min": 1600},
            {"key": "above_average", "label": "Above average", "min": 1500}],
  "teams": [{"rank": 1, "team_id": 21, "team": "…", "rating": 1754, "rank_change_7d": 2, "rating_change_7d": 12,
             "w": 10, "d": 1, "l": 1, "mp": 12, "conference": "Northeast", "conference_rank": 1,
             "tier": "elite", "badges": ["low_cross_conference"], "xconf_mp": 2, "pro_academy": false}],
  "unranked": [{"team_id": 77, "team": "…", "mp": 4, "needed": 6}]
}
```

- `GET /api/rankings/teams/{team_id}?age_group=` returns the rating history (one point per weekly
  run), the 3 biggest movers, SOS and the full delta list.
- **No run yet** (for example U15 before launch) returns **200** with `teams: []` and a `reason`.
  An unknown age group or league returns 400, and a failed read 503 (CLAUDE.md rule 1).
- `rank_change_7d` is null, not 0, when there was no run a week earlier. Absent is never zero.

### Built (SB-1808)

| Piece | Where |
|---|---|
| Read model | `backend/mt_tools/power_rating_read.py`: pure `build_rankings` / `build_team` over stored rows, and `get_power_rating` / `get_power_rating_team`, which gather through `ToolDeps.power_rating` (the `PowerRatingDAO`) |
| API | `GET /api/rankings?age_group=&league=Homegrown&season=&view=&conference=` and `GET /api/rankings/teams/{team_id}?age_group=&league=&season=`, logged-in (`get_current_user_required`) |
| mt-mcp | `get_power_rating`, `get_power_rating_team`, read tier (MT AI sees both) |
| CLI | `mt rankings U17 [-l Homegrown] [--view conference] [-c Northeast] [--json]`; `mt rankings team "IFA" --age U15` |

How the reads behave:
- **Views.** `view` defaults to `national` when the run is national, otherwise `conference`.
  A `national` request on a non-national run gets the conference lists, `view: "conference"`
  and `publication.reason`. `tiers` is non-empty, and rows carry a `tier`, in the national view
  only. In the national view, a ranked team outside the main island has `rank: null` and
  `comparable_nationally: false`. In the conference view `rank` is null and rows are ordered by
  conference, then `conference_rank`. `conferences` lists every conference in the run, which is
  what `conference=` accepts (case-insensitive); anything else is 400.
- **Movement** compares the latest run with the run users saw 7 days before it was computed
  (`run_as_of(latest.computed_at − 7 days)`, reported as `movement_since`). It is measured from
  the latest run rather than from "now", so a run's payload never changes. `rank_change_7d` is in
  the view's places (national rank, or conference rank when the team kept its conference), up is
  positive. `rating_change_7d` is the difference of the rounded ratings, so it matches the
  numbers shown. Both are null when there is no such run or the team was not in it.
- **Coverage.** `teams_in_pool` counts the teams the run rated (at least one rated match). The
  note states it, the matches counted, and how many teams have the 6 matches needed to be ranked.
- **Rows.** `rating` is rounded to an integer. `club_id`, `club_logo_url` and `pro_academy` come
  from the team's club (`clubs.pro_academy`), as the leaderboards rows do. Test teams are never
  shown. `unranked` lists teams under 6 matches, most matches first, with `needed: 6`.
- **No run** (an age group before its first run) is 200: `teams: []`, `run: null`, `reason`.
  A team with no rated match in the latest run is 200 with `in_run: false` and a `reason`.
- **Team panel.** `biggest_movers` is the 3 largest |delta| matches of the latest run, with the
  opponent, the score from the team's side (and shoot-out penalties, the match being rated a
  draw), the expected share of the points and the delta. `deltas` is every rated match, oldest
  first. `history` is one point per ISO week: the last run that week that rated the team. `sos`
  is ranked toughest first among nationally ranked teams in a national run, otherwise within
  the team's conference, because separate islands are not on one scale. An unranked team gets
  its SOS rating with no rank.
- **Caching.** `PowerRatingDAO.run_payload` (the run, its ratings, its conferences' names) is
  cached in Redis under `mt:dao:power_rating:run:<id>` for 7 days. A written run never changes,
  so nothing has to clear the key. `latest_run` and `run_as_of` stay uncached: they are how a
  new run becomes visible without the worker touching the API's Redis. A run caught between its
  row and its ratings (a counted run with no ratings yet) is served but not cached. The team
  reads are small and uncached.

## UI (Ranking tab → Power Rating)

**Row:**
- rank and team, with a conference chip carrying the conference rank ("Northeast · 1st")
- **rating** rounded ("1,642")
- movement in places and points (▲2 · +12)
- W-D-L and MP
- badge

Tier headers divide the national list. The Conference view is one tab per conference. The coverage
line sits at the top, the unranked list at the bottom, dimmed, with "4 of 6 matches".

**Team panel ("why"):**
- The 3 matches that moved the rating most, each with its score, opponent and change: "Beat Y 3–0
  (+24): expected to win 41% of the time".
- Strength of schedule: average opponent rating and where it ranks ("1,538 — 12th toughest of
  147").
- A rating-over-time sparkline.

**How it works screen:**
- The formula block above, the K and G table, and the +50 home edge.
- The cap is stated as a safeguarding rule: "winning by more than 3 earns nothing extra".
- Shoot-outs count as draws. Ratings are updated nightly after results are checked.
- The publication rule for islands.
- Worked example: a 1600 home team meets a 1500 visitor, so it is expected to take 0.70. A 2–0
  win gains 30 × 1.5 × 0.30 = **+13**. A 0–1 loss costs 30 × 0.70 = **−21**.

**Wording:**
- "MT Power Rating, from N teams in MT". Never "Top 20 in MLS NEXT".
- No public page. A logged-out deep link goes to login, then back.

### Built (SB-1809)

| Piece | Where |
|---|---|
| Sub-tab and launch gate | `frontend/src/components/ranking/RankingView.vue` |
| List | `PowerRatingPanel.vue` (filters, views, states), `PowerRatingRow.vue` (one row) |
| Formatting | `frontend/src/utils/powerRating.js`: rating, ordinal, movement, tier grouping |

- **Launch gate.** `POWER_RATING_PUBLIC = false` in `RankingView.vue`. While it is false only
  admins (`authStore.isAdmin`) get the sub-nav and a "Power Rating" sub-tab with a *Preview*
  chip; everyone else sees the Ranking tab as before (Leaderboards and the coming-soon note, no
  sub-nav). Launching is setting it to `true`, which drops the chip and shows the sub-tab to every
  viewer. Remove the coming-soon note in the same change. The admin's Power Rating sub-tab does not
  show the note.
- **Views.** The API picks the view. On a national run a *National / By conference* filter is
  offered; on a run that is not, the conference lists are the only view and the panel shows
  `publication.reason` as "Not yet comparable nationally: …". The conference tabs come from
  `conferences`; the list is filtered client-side, so switching conference is not a request.
- **National list.** Tier headers in the order of `tiers`, with their cut-offs ("Elite · 1,700+").
  Ranked teams below the lowest cut-off go under *Others · below 1,500*. Teams outside the main
  island (`comparable_nationally` false) go last under their own header, without a rank.
- **Movement.** "▲2 · +12" / "▼1 · −8". No run a week earlier (`movement_since` null) shows nothing;
  a team the earlier run did not have shows *New*. A held place drops the arrow and keeps the
  points; never "▲0".
- **Unranked** teams are listed below, dimmed, as "4 of 6 matches", filtered to the conference in
  the conference view. No run is an empty state with the API's `reason`; a 4xx/5xx is an error
  with Retry.
- **View matches** (in the team panel since SB-1810; it was the row click) opens Matches as the
  leaderboards do. The rankings answer carries names only,
  so the panel resolves the age group, league and season ids from `/api/age-groups`,
  `/api/leagues` and `/api/seasons`; a failed lookup leaves that filter unset.
- The age-group choice is not remembered across visits, the same as Leaderboards; the filter
  panel's open/closed state is (`FilterPanel view="ranking"`).

### Built (SB-1810)

| Piece | Where |
|---|---|
| Team panel ("why") | `frontend/src/components/ranking/PowerRatingTeamPanel.vue`, over `GET /api/rankings/teams/{id}` |
| Formatting | `powerRating.js`: `formatMover`, `formatDelta`, `formatSos`, `sparkline`, `BADGE_EXPLANATIONS` |

- **Opening.** Tapping a row expands the panel inline beneath it (`aria-expanded` on the row).
  One panel is open at a time; a second tap, *Close* or Escape closes it and focus returns to
  the row. Changing age group, view or conference closes it. *View matches* inside the panel is
  the old row click: Matches on that team.
- **Movers.** "Beat Solar SC 3–0 · +24", then "Nov 2 · expected to take 41% of the points".
  `expected` is a share of the points (a draw counts half), so it is never worded as a chance of
  winning. A shoot-out keeps its regulation score: "Drew with … 2–2", "Won 4–3 on penalties, rated
  as a draw". A score the match row no longer has is left out, never shown as 0–0. The line is not
  clamped, because the score ends it.
- **Strength of schedule.** "Average opponent 1,538 — 12th toughest of 147"; a conference-scoped
  rank adds "in Northeast". No rank (an unranked team) states the average only.
- **Rating over time.** An inline SVG line over `history`, first and last values labelled, with an
  `aria-label` stating both. One weekly point shows the value alone.
- **Badges** are written out: provisional is fewer than 8 rated matches, low cross-conference is
  fewer than 3 matches outside its conference; pro academy does not change the rating.
- **States.** Skeleton while loading; a failure is an error with Retry; `in_run: false` shows the
  API's `reason`. Answers are cached by the list per team, age group, league and season for the
  life of the tab, so reopening a team is not a request. Failures are not cached.

### Built (SB-1811)

| Piece | Where |
|---|---|
| How it works screen | `frontend/src/components/ranking/PowerRatingHowItWorks.vue`, opened by *How it works* in the list header (`PowerRatingPanel.vue`) |
| The per-match formula | `frontend/src/utils/powerRatingModel.js`: `expectedScore`, `marginFactor`, `ratingChange` |

- **Overlay.** Teleported to `<body>` at `z-[1300]`, like the manager roles page. Closes on ✕,
  backdrop or Escape; focus goes to ✕ on open and back to the link on close.
- **Worked example is computed**, not typed: the screen renders the 1,600-vs-1,500 example
  through `powerRatingModel.js`, and a test holds it to +13 and −21. The backend job stays the
  rating of record; change both if the model changes.
- **Copy rules.** The source line reads "MT Power Rating, from N U17 teams in MT"
  (`coverage.teams_in_pool`). The screen never says "official" or "games", and makes no date
  promise: it names MLS NEXT Fest as what connects conferences, not when.

## Validation: the Fest backtest (gate before launch)

1. **Freeze Elo beside the 26b freeze:** `python -I elo_backtest.py freeze-elo
   results_2026-11-26b.csv <26b dir>` writes `elo_<age>.csv` and `elo_params.txt`. The existing
   `ratings_<age>.csv` and `ratings.py score` are untouched; both were smoke-tested.
2. **After Dec 13, export the Fest matches:** `tournament_id = 9`, status `completed`, U15–U19, both
   sides in pool. It has 0 matches today. Columns: `age_group, home_team_id, away_team_id,
   home_score, away_score` (regulation; penalties are draws). Report how many Fest matches could
   not be matched to an in-pool team id. Duplicate team rows from Fest ingest would silently
   shrink n.
3. **Score:** `ratings.py score <dir> fest.csv` gives ppg/gdpg/massey, as before.
   `elo_backtest.py score <dir> fest.csv` adds elo, with Wilson CIs, split same-island vs
   cross-island. Both models are scored raw across islands, where each island is assumed to
   average 1500; that assumption is exactly what Fest tests.
4. **Decision rule:**
   - Publish Elo if it beats PPG on cross-conference Fest matches and is within CI of Massey.
   - If Massey beats Elo by more than 3 points with a CI that excludes 0, bring it back to the
     owner. Both models are already built.
5. **Re-check with Fest in the stream:**
   - the Fest K multiplier {1.0, 1.25, 1.5}, scored on Dec–Jan matches
   - the HFA re-fit
   - the tier cut-offs
   - each age group's publication state
   - rank stability

## Coming-soon copy (SB-1803)

> **Power Rating — coming soon.** One rating for every Homegrown team from U15 to U19, built from
> results and opponent strength. It appears once MLS NEXT Fest results connect the conferences.

(It promises only what this design commits to: the ages, results-based, and a launch after Fest.
No date, no "national ranking" claim.)

## Delivery slices

| # | Slice | Ships | Est |
|---|-------|-------|----:|
| 0 | Coming-soon note on the Ranking tab (SB-1803) | copy above | 1 |
| 1 | Engine: `mt_tools/power_rating.py`, which is pure (Elo, islands, badges, tiers, SOS, deltas, Massey audit), plus tests per state (unranked / provisional / low cross-conference / ranked; absent ≠ 0). The backtest script moves to `scripts/` | unit-tested library | 3 |
| 2 | Fest backtest: export, score, write results into this doc, re-tune the Fest multiplier and tiers | go / no-go per age | 2 |
| 3 | Storage + job: migration (3 tables), backup registry, Celery beat on the k3s worker, admin recompute | nightly runs in prod | 5 |
| 4 | Reads: `GET /api/rankings` + team detail, mt-mcp `get_power_rating`, `mt rankings` | API + CLI | 3 |
| 5 | Web list: national / conference views, badges, tiers, coverage, unranked | Ranking → Power Rating | 5 |
| 6 | Team "why" panel: biggest movers, SOS, history | team drill-down | 3 |
| 7 | How it works screen | explainer | 2 |
| 8 | Admin audit: Elo vs Massey gaps above 30 places | admin view | 2 |
| 9 | June 2027: Cup weight test, season rollover (0.3 carry, U15→U16 by `team_id`) | next-season seed | 2 |

Order: 0 now; 1 before Dec 13; 2 right after Fest; 3–5 make the first usable release; 6–8 follow;
9 in June. Total 28.

## Open decisions for the owner

1. **Model.** *Recommend:* Elo published, Massey nightly audit, gated on the Fest backtest
   (decision rule above).
2. **Parameters.** *Recommend:* one K = 30 for League, Flex and tournaments, K×2 for the first 8
   matches, cap 3, home +50. This replaces the brief's 20/25/30/35 and +75.
3. **When a national list shows.** *Recommend:* only when one island holds ≥90% of teams and every
   conference has ≥5 cross-conference matches. Otherwise conference lists only. Launch after Fest.
4. **Pro academies.**
   - *Recommend:* rank PPP-conference teams with a "Pro academy" tag.
   - *Recommend:* exclude matches against out-of-pool sides (brief §8 rule). Today that drops 96
     matches and changes no island.
5. **Tiers.** *Recommend:* three labelled tiers (Elite 1700+, Contender 1600+, Above average 1500+)
   and no label below 1500, rather than the brief's "Developing" for about half of all teams.
6. **Season rollover.** *Recommend:* carry 30% (brief: 70%), keep the provisional K, and re-test in
   September 2027.
7. **Where the job runs.** *Recommend:* Celery beat on the k3s worker, plus an admin recompute
   endpoint.
8. **Cup weights.** *Recommend:* GA Cup and MLS NEXT Cup at the same K, neutral venue, in-pool
   matches only. Revisit 35 against the June 2027 Cup.
9. **Forfeits.** *Recommend:* not rated (no match was played), though the leaderboards still count
   them.
