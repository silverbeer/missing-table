# Match Tracking CLI (mt)

Chat with Claw during matches to post live events to MissingTable.

## Setup

### 1. Add BACKEND_URL to .env.prod

For prod environment (MacBook Air at matches), add this line to `backend/.env.prod`:

```bash
BACKEND_URL=https://your-production-api-url.com
```

### 2. Choose an Environment

For one command, use the flag. Nothing is written to disk:

```bash
mt --env prod team matches "IFA U15"
```

To move for a whole session, set the persistent mode. This redirects **every**
later `mt` command, in this shell and every other one, until it is changed back
— and `.mt-config` is read by `cache_cli.py` and `switch-env.sh` too:

```bash
./switch-env.sh local    # at home (Mac mini) - default
./switch-env.sh prod     # at a match (MacBook Air)
```

Precedence is `--env` > `APP_ENV` > `.mt-config` > `local`. `mt config` prints
the resolved environment and which of those decided it, and any command aimed
somewhere other than local announces itself before it runs.

### 3. Install the CLI

```bash
cd backend
uv pip install -e .
```

This registers the `mt` command from `mt_cli.py`.

## Command Reference

### Authentication

```bash
mt login [username]    # Login (default: tom)
mt logout              # Clear credentials for the targeted environment
mt config              # Show current config + active match
```

Sessions are stored per environment, so a prod login is never sent to a local
API and an active prod match is not mistaken for a local one. Logging in to one
does not log you out of the other.

### Search for Matches

```bash
mt search                        # Next 7 days
mt search --age U14              # Filter by age group
mt search --team IFA             # Filter by team name
mt search --days 30              # Extend date range
mt search --age U14 --team IFA   # Combine filters
```

### Live Match Tracking

All match commands use a stored `match_id` — no need to repeat it.

```bash
mt match start <match_id>                    # Start tracking (stores match_id)
mt match start <match_id> --half 35          # Custom half duration

mt match goal --team home                    # Home team goal
mt match goal --team away --player "Matt"    # Away goal with scorer
mt match goal --team IFA --player 7          # By team name + jersey #

mt match message "Great pass by Carter"      # Post a chat message

mt match status                              # Score, period, minute, events

mt match halftime                            # End first half
mt match secondhalf                          # Kick off second half
mt match end                                 # Full time (clears match_id)
```

## Match Day Workflow

### At Home (Mac mini)

```bash
cd /Users/silverbeer/gitrepos/missing-table

# Start backend if not running
./missing-table.sh start

cd backend
mt login
mt search --age U14 --days 7
mt match start 1053
mt match goal --team home --player "Matt"
mt match message "Nice save by keeper"
mt match halftime
mt match secondhalf
mt match goal --team away
mt match end
```

### At Match (MacBook Air)

```bash
cd /Users/silverbeer/gitrepos/missing-table

# Switch to prod (one time)
./switch-env.sh prod

cd backend
mt login
mt search --age U14
mt match start 1053
mt match goal --team home --player "Matt"
mt match status
mt match end
```

## Integration with Claw

When chatting with Claw during a match:

**You:** Match started, it's match 1053
**Claw:** *(runs `mt match start 1053`)*

**You:** Goal. IFA. Matt scored
**Claw:** *(runs `mt match goal --team IFA --player "Matt"`)*

**You:** What's the score?
**Claw:** *(runs `mt match status`)* IFA 1 - 0 Revolution

**You:** It's halftime
**Claw:** *(runs `mt match halftime`)*

**You:** Game over
**Claw:** *(runs `mt match end`)*

## Architecture

```
You (via chat)
    |
Claw (OpenClaw)
    |
mt CLI (mt_cli.py)
    |
FastAPI Backend (localhost:8000 or prod)
    |
Supabase Database
```

## Configuration Files

- **`.mt-config`** - Environment setting (local/prod) - shared with `switch-env.sh`
- **`.mt-cli-state.json`** - Login session + active match state, keyed by environment (gitignored)
- **`.env.local`** - Local dev config (BACKEND_URL, Supabase credentials)
- **`.env.prod`** - Production config (add BACKEND_URL here)

## Troubleshooting

### "Not logged in"

```bash
mt login
```

### "No active match"

Start tracking first:
```bash
mt match start <match_id>
```

### "BACKEND_URL not set in .env.prod"

Add to `backend/.env.prod`:
```bash
BACKEND_URL=https://your-api-url.com
```

### "Connection error"

- **Local:** Make sure backend is running (`./missing-table.sh status`)
- **Prod:** Check BACKEND_URL in `.env.prod`, verify network connectivity
