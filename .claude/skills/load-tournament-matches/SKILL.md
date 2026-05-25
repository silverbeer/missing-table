---
name: load-tournament-matches
description: Load a tournament's bracket and results into Missing Table from a pasted screenshot. Extracts matches, teams, and logos via vision; confirms each club/team with the user before creating; then upserts the matches into the tournament — creating new matchups and filling in scores on matches that already exist. Use when the user pastes a screenshot of a tournament results / bracket page (mlssoccer.com, GotSport, etc.), including follow-up screenshots that add scores to a round you already loaded.
allowed-tools: Bash, Read
---

# Load Tournament Matches

This skill loads a tournament's matches into Missing Table from a screenshot. It handles the **full richness** flow: it creates missing clubs (with cropped logos) and teams, then **upserts** the matches into the tournament. Resolution is human-confirmed at every fuzzy step — nothing is silently created or overwritten.

**Upsert, not just insert.** A round's scores rarely arrive all at once. The typical loop is: load the matchups (scheduled, no scores) → later upload a screenshot where some scores are in → later again with more scores → then the next round's matchups, and repeat. So every run *reconciles* the screenshot against what's already in the tournament: it **creates** matchups that don't exist yet, **fills in scores** on matches that exist but aren't scored, leaves already-correct matches **untouched**, and **flags** (never silently overwrites) any match whose existing score disagrees with the screenshot.

## Prerequisites — check these BEFORE doing anything else

1. **A pasted screenshot must be in the current message.** If not, ask the user to paste one.

2. **Verify authentication** by running:
   ```bash
   cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py auth status
   ```

   The response is JSON. Possible outcomes:

   - `{"authenticated": true, "role": "admin", ...}` → proceed.
   - `{"authenticated": true, "role": "not_admin", ...}` → STOP. The cached token belongs to a non-admin user (e.g. team-manager). Admin endpoints will fail. Tell the user to log out and log in again as an admin:
     ```
     ! cd backend && uv run python mt_cli.py logout && uv run python mt_cli.py login <admin-username>
     ```
   - `{"authenticated": false, "hint": "..."}` → ask the user which MT admin username they want to log in as, then tell them to run (note the `!` prefix — required so `getpass` can prompt for the password in their terminal):
     ```
     ! cd backend && uv run python mt_cli.py login <username>
     ```
     Once they confirm login succeeded, re-run `auth status` to verify.

3. **`MT_API_BASE_URL`** (optional, defaults to `http://localhost:8000`). The skill **shares its token with `backend/mt_cli.py`** via `backend/.mt-cli-state.json` — log in once with `mt_cli`, both tools use it. `MT_ADMIN_TOKEN` env var overrides the cached token if you want to use a different one for the skill specifically.

## Tool location

All operations go through one CLI. Always invoke from `backend/` so the script picks up MT's venv (which already has typer + pillow + httpx + pydantic + the `api_client` package on the path):

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py <subcommand> [args]
```

Every subcommand prints JSON to stdout. Errors print JSON to stderr and exit non-zero.

Quick subcommand map:

| Goal | Command |
|------|---------|
| Check authentication + admin role | `auth status` |
| Show age groups, divisions, seasons, active tournaments in one shot | `refdata show` |
| Look up an MLS NEXT club's division by name + age group | `clubmap lookup --team "<name>" --age-group U14` |
| Find a club by name (local fuzzy match) | `club find "<name>"` |
| Create a club | `club create --name --city [--description]` |
| Crop a logo region out of the screenshot | `logo crop --image --bbox x,y,w,h --output` |
| Upload a logo to a club | `logo upload --club-id --path` |
| Look up a team (admin endpoint with exact + similar) | `team lookup "<name>"` |
| Create a team | `team create --name --city --age-group-id --division-id [--club-id] [--academy-team]` |
| Find a tournament by name | `tournament find "<name>"` |
| List a tournament's existing matches (for upsert mapping) | `tournament matches <tournament_id>` |
| Create a tournament | `tournament create --name --start-date [--end-date --age-group-ids 1,2,3]` |
| Add a match to a tournament | `match create --tournament-id --our-team-id --opponent-name --match-date --age-group-id --season-id [--home-score ... --tournament-round ...]` |
| Update an existing match (fill in scores/status) | `match update --tournament-id --match-id [--home-score ... --away-score ... --match-status completed ...]` |

## Workflow

### Step 1 — extract from the screenshot

Look at the pasted image and pull out:

- **Tournament name** (e.g. "2026 MLS Next Cup Championship") and overall **date range** if shown.
- For each match row: **kickoff date/time**, **home team name**, **away team name**, **regulation score**, **penalty-shootout score** (if visible — usually shown as "(5–4 pens)" or similar), **age group** (U13/U14/...), **bracket round** (group stage, QF, SF, final, etc.), the **bracket / group label**, and the **bracket position** (top-to-bottom).
  - **Bracket name is mandatory for bracket-round matches** (`round_of_32`/`round_of_16`/`quarterfinal`/`semifinal`/`final`/`third_place`). MLS Next Cup, for example, has a **Championship** bracket and a **Premier** bracket — and the bracket name lives in the same field as group-stage labels (`tournament_group`). The frontend bracket UI filters strictly on this value: a bracket-round match with no `tournament_group` is invisible in the bracket view, even if all the team data is correct.
  - Source clues: the screenshot's heading ("MLS NEXT Cup Championship 2026" → `Championship`), tab/pill above the bracket ("Premier" / "Silver" / "Bronze"), or the URL slug on the source page (`/championship/u15`). If the screenshot only shows the bracket sub-section without naming it, **ask the user which bracket this is** before creating matches — don't guess.
  - For group-stage matches the same field holds the group letter ("A", "B", "C", ...). The convention is one of: a bracket name, a group letter, or `null` for ungrouped one-off rounds.
  - **Bracket position (`tournament_round_order`) is mandatory for bracket-round matches.** This is the 0-based top-to-bottom index of the match within its round on the source bracket. Top of the bracket = 0; immediately below = 1; etc. Without this field set, the frontend falls back to `id`-order — which only happens to match the canonical layout when matches were loaded in bracket order. If they weren't (e.g. you re-load some matches later, or rounds were loaded out of order), the bracket connectors point at the wrong feeder matches even though the data is otherwise correct. Read the position straight off the screenshot — the order in which match cells appear top-to-bottom on the source bracket is the position you set. Standard pairing convention: R32 slots `(2k, 2k+1)` feed into R16 slot `k`, etc.
- For each unique team that appears: an approximate **logo bounding box** (`x,y,width,height` in pixels) you can extract from the screenshot.

Show the user a tight summary table of what you found and **ask them to confirm before doing any writes**. This is the single biggest moment to catch parsing errors.

### Step 2 — load reference data

Once confirmed, fetch the IDs you'll need:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py refdata show
```

Build name → id maps in your head for `age_groups`, `divisions`, `seasons`, and `tournaments`. You'll need the current season's `id`, age group IDs for each match, and a `division_id` if you create any new teams.

### Step 3 — verify or create the tournament

Search:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py tournament find "<name>"
```

If `exact` is non-null, use that `id`. Otherwise show the `similar` list to the user.

- If the user confirms a similar match is the same tournament, use it.
- If it's truly new, get user confirmation and run:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py tournament create \
  --name "..." --start-date YYYY-MM-DD [--end-date YYYY-MM-DD] \
  [--age-group-ids 3,4,5] [--location "..."] [--description "..."]
```

### Step 4 — resolve every team (lookup → confirm → create)

For each unique team name in the matches:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py team lookup "<team name>"
```

Response shape: `{"exact": team | null, "similar": [team, ...]}`.

- **`exact` is non-null** → use that team's `id`. Done.
- **`exact` is null, `similar` is non-empty** → show the candidates to the user. **Always wait for explicit confirmation** — never auto-pick a similar match. The user picks one OR says "no, create new".
- **No matches** → ask the user to confirm creating a new club + team. Then:

  1. **Look up the team in the MLS NEXT clubs mapping** to find its canonical division and pro-academy status. The mapping (`backend/data/mls-next-clubs.json`) covers all current MLS NEXT Allstate Homegrown + Pro Player Pathway teams:
     ```bash
     cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py clubmap lookup \
       --team "<team name>" --age-group U14
     ```
     - **`match` is non-null** → use `match.division` as the division for team creation (find its `id` via `refdata show`'s divisions list — match by name; if the MT division doesn't exist yet, surface that to the user). Use `match.is_pro_academy` to set `--academy-team`.
     - **`match` is null, `all_age_groups_for_team` is non-empty** → the team plays at *other* age groups but not this one. Surface to the user — the screenshot may have a typo or the roster has changed.
     - **No matches at all** → not an MLS NEXT Allstate Homegrown / PPP team. Ask the user for division + whether it's a pro academy.

  2. **Crop the logo** out of the screenshot using the bbox you extracted in Step 1:
     ```bash
     cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py logo crop \
       --image /path/to/pasted-screenshot.png \
       --bbox X,Y,W,H \
       --output /tmp/logo_<slug>.png
     ```

  3. **Create the club** (idempotent — duplicate name returns the existing club row with HTTP 200):
     ```bash
     cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py club create \
       --name "..." --city "..."
     ```
     Capture the returned `id`. No need for `club find` first — the endpoint handles duplicates.

  4. **Upload the logo**:
     ```bash
     cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py logo upload \
       --club-id <id> --path /tmp/logo_<slug>.png
     ```

  5. **Create the team** (idempotent — duplicate `(name, division_id)` returns the existing team row):
     ```bash
     cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py team create \
       --name "..." --city "..." \
       --age-group-id <id> --division-id <id> \
       --club-id <club_id> \
       [--academy-team]    # pass if clubmap.match.is_pro_academy was true
     ```
     The response is `{"message": "...", "team": {row}}`. Parse `team.id` directly — no follow-up `team lookup` needed.

Keep a running map of resolved `team name → team id` so you don't lookup the same team twice across multiple matches.

### Step 5 — reconcile the screenshot against existing matches

**Before writing anything, find out what's already in the tournament.** This is what turns the skill from insert-only into upsert and lets the user upload scores in waves.

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py tournament matches <tournament_id>
```

This returns `{"matches": [{id, match_date, match_status, tournament_round, home_team:{id,name}, away_team:{id,name}, home_score, away_score, home_penalty_score, away_penalty_score}, ...]}`.

**Match each screenshot row to an existing match** by `match_date` + the **pair of team names** (compare the existing `home_team.name`/`away_team.name` against the screenshot names using the same normalization you used for team resolution in Step 4 — and the team `id`s you already resolved, when the side is a tracked team). Within one round on one date a pairing is unique, so this is reliable. **If a row is ambiguous (matches zero or several), show it to the user and ask — never guess.**

For each screenshot row, classify it and act per this table:

| Situation | Action |
|-----------|--------|
| **No existing match** for this pairing/date | **Create** it — go to Step 6 (create). |
| Exists, **no score yet** (`home_score`/`away_score` null, status `scheduled`), screenshot has a score | **Update** it — Step 6 (update). |
| Exists, **already scored identically** to the screenshot | **Skip** (no-op). Report as "already correct". |
| Exists, **scored differently** from the screenshot | **Flag — do NOT overwrite.** List it for the user (existing vs. screenshot) and let them decide. Only update if they explicitly confirm. |
| Exists, still no score in the screenshot either | **Skip** — nothing to do yet. |

Build the create-list and update-list, show the user a short plan ("N to create, M to score, K already correct, J conflicts to review"), and proceed once confirmed.

**Bracket sanity checks (mandatory).** Before sending any creates/updates for bracket-round matches, scan the planned writes:

1. **`tournament_group`** — any row where `tournament_round` is in (`round_of_32`/`round_of_16`/`quarterfinal`/`semifinal`/`final`/`third_place`) but `tournament_group` is null/empty. If any are found, stop and ask the user which bracket those matches belong to (Championship / Premier / Silver / Bronze / etc.) and apply the answer to every such row. Frontend filter is `m.tournament_group === selectedGroup`, so a null group renders as invisible.
2. **`tournament_round_order`** — any bracket-round row without an explicit position. If you can read positions off the screenshot, set them yourself (0-based top to bottom within the round + bracket). If the screenshot is ambiguous or you only loaded a partial round, stop and confirm with the user. Frontend falls back to `id`-order without this, which produces the wrong layout when ids don't match canonical bracket order.

### Step 6 — create or update each match

**Create** a match that doesn't exist yet:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py match create \
  --tournament-id <id> \
  --our-team-id <one-of-our-tracked-teams> \
  --opponent-name "<the other team's name as a string>" \
  --match-date YYYY-MM-DD \
  --age-group-id <id> \
  --season-id <id> \
  --home/--away \
  [--home-score 2 --away-score 1] \
  [--home-penalty-score 5 --away-penalty-score 4] \
  [--match-status completed|scheduled|in_progress] \
  [--tournament-round group_stage|round_of_32|round_of_16|quarterfinal|semifinal|final|third_place|wildcard|silver_semifinal|bronze_semifinal|silver_final|bronze_final] \
  [--tournament-group "A" | "Championship" | "Premier" | ...]   # group letter for group_stage, bracket name for everything else; required for bracket rounds \
  [--tournament-round-order N]   # 0-based top-to-bottom slot within the round; required for bracket rounds (R32 0..15, R16 0..7, QF 0..3, SF 0..1, Final 0) \
  [--scheduled-kickoff "2026-06-21T15:00:00Z"]
```

**Update** an existing match to fill in (or, with user confirmation, correct) its score. Use the `id` from `tournament matches`. Only the flags you pass change; everything else is left alone:

```bash
cd backend && uv run python ../.claude/skills/load-tournament-matches/scripts/mt.py match update \
  --tournament-id <id> \
  --match-id <existing match id> \
  --home-score 2 --away-score 1 \
  --match-status completed \
  [--home-penalty-score 5 --away-penalty-score 4] \
  [--tournament-round round_of_16] [--tournament-group "A"] \
  [--scheduled-kickoff "2026-06-21T15:00:00Z"] [--match-date YYYY-MM-DD] \
  [--swap-home-away]
```

**Important semantics:**

- **Create** takes `our_team_id` (an existing tracked team) + `opponent_name` (a string). The backend auto-resolves the opponent: exact-match an existing team, otherwise create a lightweight tournament-only team. So you don't have to create both sides as full teams — only the "our team" side needs to be a real tracked team. **Update** works on the match `id` directly and never touches team identities (unless you pass `--swap-home-away` to fix a reversed fixture).
- For **MLS Next Cup specifically**: the user is loading the bracket to make the tournament look great in MT, but their own team may not be in it. So most matches will have `opponent_name` pointing to an opposing team and `our_team_id` pointing to whatever tracked team is closest. If neither team is "ours", pick the home team to be `our_team_id` and let `is_home=True`.
- **Penalty shootout scores** are only valid when the regulation score is a draw. Always pass both `--home-penalty-score` and `--away-penalty-score` together or neither — on both create and update.
- **`match_status`**: when a score is final use `completed`; a not-yet-played matchup is `scheduled`. When filling in a score on a previously-scheduled match, pass `--match-status completed` alongside the scores.
- The orientation matters: scores are **home : away**. If the screenshot's home team is the existing match's away team, either map the scores accordingly or use `--swap-home-away`.

### Step 7 — summary

Print a single summary block at the end:

```
Tournament:        <name> (id=N)         [created | reused]
Clubs created:     <count> — names...
Teams created:     <count> — names...
Logos uploaded:    <count>
Matches created:   <count>
Matches updated:   <count> — scores filled in
Already correct:   <count> — skipped
Conflicts:         <count> — listed for review (NOT changed)
Match link:        <MT_API_BASE_URL>/tournaments/<id>
```

If any step failed (e.g. a logo upload returned non-2xx), surface it explicitly — don't bury errors.

## Resilience guidance

- **Idempotency**: every helper does a lookup before insert, and Step 5 reconciles against existing matches before any write. Re-running the skill on the same screenshot should be a no-op — already-scored matches report as "already correct", not duplicated or re-written.
- **Errors**: API errors print JSON to stderr with `status_code` and `response`. Surface them to the user instead of retrying blindly.
- **Logo dedup**: if the same club appears across multiple age groups in one screenshot, crop and upload the logo once. Track which clubs you've already processed.
- **Don't auto-pick fuzzy matches**: the team-lookup endpoint exists specifically so you can confirm before any create. Use it.

## Out of scope

- This skill does **not** scrape mlssoccer.com directly. Input must be a pasted screenshot.
- This skill creates and **updates** matches (scores, status, round/group, kickoff, home/away swap) but does **not delete** them. Use a future `mt-crud` skill for deletion (see https://github.com/silverbeer/missing-table/issues/347).
