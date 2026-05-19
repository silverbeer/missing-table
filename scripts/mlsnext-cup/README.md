# MLS NEXT Cup load artifacts

Inputs and a load script for the 2026 MLS NEXT Cup tournament data.
Used by:

- **SB-27** — tournament bracket UX feature (validates the data via the
  bracket render against local MT)
- **SB-28** — prod load of the same matches (blocked by SB-27)

## Contents

| Path | What |
|------|------|
| `sched/championship_U13.json` | 25 row-blocks: 16 real R32 matches + 9 TBD placeholders |
| `sched/championship_U14.json` | 25 row-blocks: 16 real + 9 TBD |
| `sched/championship_{U15,U16,U17,U19}.json` | empty arrays — those age groups have no MLS NEXT Cup playoff schedule yet |
| `sched/premier_U13.json` | 25 row-blocks: 16 real + 9 TBD |
| `sched/premier_U14.json` | 25 row-blocks: 16 real + 9 TBD |
| `sched/premier_{U15,U16,U17,U19}.json` | empty arrays |
| `load_cup.py` | The loader. Idempotent for clubs+teams (lookup-first); **NOT** idempotent for matches. |

64 real round_of_32 matches total across both brackets at U13 and U14.

## Source

Scraped from `https://www.modular11.com/events/event/iframe/schedule/<bracket>/87/<age_group_id>/1`
on 2026-05-19 via Playwright. The `87` is the MLS NEXT Cup event id; age
group IDs in modular11 are: 21=U13, 22=U14, 33=U15, 14=U16, 15=U17, 26=U19.

Each row in the JSON files is one schedule entry with fields:
`match_id, date, time, venue, age_group, bracket, round_label, home, score, away`.

## Running the loader

Always `--dry-run` first against any environment.

```bash
# Local (matches were originally loaded this way)
cd backend && uv run python ../scripts/mlsnext-cup/load_cup.py \
  --base http://localhost:8000 --dry-run

# Prod (requires `./switch-env.sh prod` and a prod mt_cli login)
cd backend && uv run python ../scripts/mlsnext-cup/load_cup.py \
  --base https://api.missingtable.com --division-mapping prod --dry-run
```

Then re-run with `--write` to apply.

## Known caveats

- **Match create is NOT idempotent** — re-running `--write` will create
  duplicate match rows in the target environment.
- **Logos are NOT loaded.** The modular11 schedule iframe has no `<img>`
  tags. The bulk of clubs have no logo in MT after this load.
- **Cities default to `—`** for newly-created clubs. The script does a
  team lookup first, so existing clubs in the target environment keep
  their existing cities.
- Local + prod use **different division IDs**. The script picks the right
  map via `--division-mapping local|prod`. Verify against `refdata show`
  before `--write` in a new environment.
