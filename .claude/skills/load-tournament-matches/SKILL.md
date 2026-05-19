---
name: load-tournament-matches
description: Load a tournament's bracket and results into Missing Table from a pasted screenshot. Extracts matches, teams, and logos via vision; confirms each club/team with the user before creating; then POSTs the matches to the tournament. Use when the user pastes a screenshot of a tournament results / bracket page (mlssoccer.com, GotSport, etc.).
allowed-tools: Bash, Read
---

# Load Tournament Matches

This skill loads a tournament's matches into Missing Table from a screenshot. It handles the **full richness** flow: it creates missing clubs (with cropped logos) and teams, then POSTs the matches to the tournament. Resolution is human-confirmed at every fuzzy step — nothing is silently created.

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
| Create a tournament | `tournament create --name --start-date [--end-date --age-group-ids 1,2,3]` |
| Add a match to a tournament | `match create --tournament-id --our-team-id --opponent-name --match-date --age-group-id --season-id [--home-score ... --tournament-round ...]` |

## Workflow

### Step 1 — extract from the screenshot

Look at the pasted image and pull out:

- **Tournament name** (e.g. "2026 MLS Next Cup Championship") and overall **date range** if shown.
- For each match row: **kickoff date/time**, **home team name**, **away team name**, **regulation score**, **penalty-shootout score** (if visible — usually shown as "(5–4 pens)" or similar), **age group** (U13/U14/...), **bracket round** (group stage, QF, SF, final, etc.), and any **group label** ("Group A").
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

### Step 5 — create each match

For every match in the screenshot:

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
  [--tournament-group "A"] \
  [--scheduled-kickoff "2026-06-21T15:00:00Z"]
```

**Important semantics:**

- The endpoint takes `our_team_id` (an existing tracked team) + `opponent_name` (a string). The backend will auto-resolve the opponent: exact-match an existing team, otherwise create a lightweight tournament-only team. This means you don't have to create both sides as full teams — only the "our team" side needs to be a real tracked team.
- For **MLS Next Cup specifically**: the user is loading the bracket to make the tournament look great in MT, but their own U14 IFA team is not in it. So most matches will have `opponent_name` pointing to an opposing team and `our_team_id` pointing to whatever tracked team is closest. If neither team is "ours", pick the home team to be `our_team_id` and let `is_home=True`.
- **Penalty shootout scores** are only valid when the regulation score is a draw. Always pass both `--home-penalty-score` and `--away-penalty-score` together or neither.
- **`match_status`**: use `completed` if the score is final, otherwise `scheduled`.

### Step 6 — summary

Print a single summary block at the end:

```
Tournament:        <name> (id=N)         [created | reused]
Clubs created:     <count> — names...
Teams created:     <count> — names...
Logos uploaded:    <count>
Matches created:   <count>
Match link:        <MT_API_BASE_URL>/tournaments/<id>
```

If any step failed (e.g. a logo upload returned non-2xx), surface it explicitly — don't bury errors.

## Resilience guidance

- **Idempotency**: every helper does a lookup before insert. Re-running the skill on the same screenshot should be a no-op (or it should report "already exists" cleanly).
- **Errors**: API errors print JSON to stderr with `status_code` and `response`. Surface them to the user instead of retrying blindly.
- **Logo dedup**: if the same club appears across multiple age groups in one screenshot, crop and upload the logo once. Track which clubs you've already processed.
- **Don't auto-pick fuzzy matches**: the team-lookup endpoint exists specifically so you can confirm before any create. Use it.

## Out of scope

- This skill does **not** scrape mlssoccer.com directly. Input must be a pasted screenshot.
- This skill does **not** edit or delete existing matches. Use a future `mt-crud` skill for that (see https://github.com/silverbeer/missing-table/issues/347).
