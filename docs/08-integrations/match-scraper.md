# Match-Scraper Integration Guide

This guide explains how to integrate match-scraper with the Missing Table API. The system supports **three submission modes**:

- **Direct RabbitMQ (Planned)** - Match-scraper sends directly to RabbitMQ queue (most resilient)
- **Async API (Current)** - Uses RabbitMQ/Celery via HTTP API for background processing
- **Sync API (Legacy)** - Direct database operations (deprecated)

## 🏗️ Architecture Evolution

### Current Architecture (v2.0 - Async API)
```
Match-Scraper → HTTP API → Backend → RabbitMQ → Celery Workers → Database
                            ⚠️ Backend is single point of failure
```

### Target Architecture (v3.0 - Direct Queue)
```
Match-Scraper → RabbitMQ (direct) → Celery Workers → Database
               ✅ No backend dependency
               ✅ Message-based contract
               ✅ Maximum resilience
```

**Key Difference:** Match-scraper will send messages directly to RabbitMQ, eliminating backend API dependency. See [NEXT_SESSION_PLAN.md](../NEXT_SESSION_PLAN.md) for implementation details.

**Message Contract:** [match-message-schema.json](./match-message-schema.json) - JSON Schema defining the message format between producer (match-scraper) and consumer (celery workers).

## 🚀 Quick Start

### 1. Generate Service Account Token

```bash
# Generate a token for match-scraper with match management permissions
cd backend
uv run python scripts/utilities/create_service_account_token.py --service-name match-scraper --permissions manage_matches

# Example output:
# Service Account Token Generated Successfully!
#
# Service Name: match-scraper
# Permissions: manage_matches
# Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. Configure Match-Scraper

Add the generated token to your match-scraper environment:

```bash
# In match-scraper .env.local or .env.prod file
MISSING_TABLE_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
MISSING_TABLE_API_BASE_URL=http://localhost:8080  # or https://missingtable.com for prod

# Optional: Choose API mode (default is async)
USE_ASYNC_API=true  # Recommended for bulk operations
```

### 3. Run the Scraper

```bash
# Use async API (default - recommended)
python -m src.cli.main scrape -a U14 -d Northeast

# Or explicitly enable async
python -m src.cli.main scrape -a U14 -d Northeast --async-api

# Use sync API (legacy)
python -m src.cli.main scrape -a U14 -d Northeast --sync-api
```

## 🔄 Async API (Recommended)

### Why Async?

- ✅ **Faster** - Immediate response, background processing
- ✅ **Simpler** - No need to preload team caches or lookup entity IDs
- ✅ **More Resilient** - Automatic retries on failures
- ✅ **Scalable** - Multiple Celery workers process matches in parallel
- ✅ **Better Error Handling** - Failed tasks can be retried independently

### Architecture

```
Match-Scraper → POST /api/matches/submit → RabbitMQ (matches.prod)
                                              ↓
                                    missing-table-celery-worker-prod
                                              ↓
                                    Entity Resolution + Database
```

### Queue topology

There is **one queue and one worker** (SB-854):

| | |
|---|---|
| Queue | `matches.prod` |
| Publisher | `match-scraper-agent`, via `AGENT_QUEUE_NAME` |
| Consumer | `missing-table-celery-worker-prod` |
| Database | **cloud** Supabase — the system of record |

The cloud database is the only thing the queue writes to. To get production
data onto a local machine, restore a backup (`./scripts/setup-local-db.sh
--from-prod`) — never point the ingest path at a local database.

A `matches.local` queue and a second `missing-table-celery-worker-local`
deployment used to exist. The worker consumed `matches` (not `matches.local`)
and wrote to the same cloud database, so its name described neither its queue
nor its database; nothing published to `matches`, so it processed zero tasks.
Both were retired, along with the `matches-fanout` exchange binding that fed
`matches.local` without a consumer.

### API Endpoints

#### 1. Submit Match for Async Processing

**Endpoint:** `POST /api/matches/submit`

**Authentication:** Bearer token (service account)

**Request Body:**
```json
{
  "home_team": "IFA",
  "away_team": "NEFC",
  "match_date": "2025-10-15T14:00:00Z",
  "season": "2025-26",
  "age_group": "U14",
  "division": "Northeast",
  "match_status": "scheduled",
  "match_type": "League",
  "home_score": null,
  "away_score": null,
  "external_match_id": "mls-12345",
  "location": "Field 1"
}
```

**Key Differences from Sync API:**
- Uses **team names** instead of team IDs
- Uses **age group string** instead of age_group_id
- Uses **division string** instead of division_id
- Backend resolves all entities automatically

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/api/matches/task/550e8400-e29b-41d4-a716-446655440000",
  "match": {
    "home_team": "IFA",
    "away_team": "NEFC",
    "match_date": "2025-10-15T14:00:00Z"
  }
}
```

#### 2. Check Task Status

**Endpoint:** `GET /api/matches/task/{task_id}`

**Authentication:** Bearer token (service account)

**Response (Pending):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "PENDING",
  "ready": false
}
```

**Response (Success):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "SUCCESS",
  "ready": true,
  "result": {
    "match_id": 489,
    "status": "created",
    "message": "Match created successfully"
  }
}
```

**Response (Failure):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "FAILURE",
  "ready": true,
  "error": "Team not found: Unknown Team"
}
```

### Python Example

```python
import asyncio
from src.api.missing_table_client import MissingTableClient

async def submit_matches_async():
    # Initialize client
    client = MissingTableClient(
        base_url="https://missingtable.com",
        api_token="your-service-account-token"
    )

    # Health check
    health = await client.health_check()
    print(f"API Status: {health.status}")

    # Submit match
    match_data = {
        "home_team": "IFA",
        "away_team": "NEFC",
        "match_date": "2025-10-15T14:00:00Z",
        "season": "2025-26",
        "age_group": "U14",
        "division": "Northeast",
        "match_status": "scheduled",
        "match_type": "League",
        "external_match_id": "mls-12345"
    }

    # Submit for async processing
    result = await client.submit_match_async(match_data)
    task_id = result["task_id"]
    print(f"Task submitted: {task_id}")

    # Poll for completion (optional)
    max_polls = 30
    for i in range(max_polls):
        status = await client.get_task_status(task_id)

        if status["ready"]:
            if status.get("result"):
                print(f"Match created: {status['result']['match_id']}")
                return status["result"]["match_id"]
            elif status.get("error"):
                print(f"Task failed: {status['error']}")
                return None

        await asyncio.sleep(1)

    print("Task timeout - still processing")
    return None

# Run
asyncio.run(submit_matches_async())
```

### Curl Examples

```bash
# 1. Health check (no auth required)
curl https://missingtable.com/health

# 2. Submit match for async processing
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://missingtable.com/api/matches/submit \
     -d '{
       "home_team": "IFA",
       "away_team": "NEFC",
       "match_date": "2025-10-15T14:00:00Z",
       "season": "2025-26",
       "age_group": "U14",
       "division": "Northeast",
       "match_status": "scheduled",
       "match_type": "League",
       "external_match_id": "mls-12345"
     }'

# 3. Check task status
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://missingtable.com/api/matches/task/TASK_ID_HERE
```

## 🔄 Sync API (Legacy)

The synchronous API is still available for backward compatibility but is **not recommended** for bulk operations.

### Limitations of Sync API

- ⚠️ Slower - waits for each operation to complete
- ⚠️ Complex - requires entity ID lookups before submission
- ⚠️ Less resilient - no automatic retries
- ⚠️ No parallelization - processes one match at a time

### Endpoints

#### Create Match

**Endpoint:** `POST /api/matches`

**Request Body:**
```json
{
  "match_date": "2025-10-15",
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 0,
  "away_score": 0,
  "season_id": 1,
  "age_group_id": 2,
  "match_type_id": 1,
  "division_id": 1
}
```

**Note:** Requires looking up IDs first via reference data endpoints.

#### Update Match

**Endpoint:** `PUT /api/matches/{match_id}`

**Request Body:** Same as create, with updated scores

#### Get Matches

**Endpoint:** `GET /api/matches`

**Query Parameters:**
- `season_id` - Filter by season
- `age_group_id` - Filter by age group
- `team_id` - Filter by team
- `external_match_id` - Find by external ID

### Reference Data Endpoints

Before using sync API, you need to look up entity IDs:

```bash
GET /api/teams          # Get team IDs
GET /api/seasons        # Get season IDs
GET /api/age-groups     # Get age group IDs
GET /api/match-types    # Get match type IDs
GET /api/divisions      # Get division IDs
```

## 🔐 Authentication & Security

### Service Account Features

- **Limited Scope**: Only `manage_matches` permission
- **No User Access**: Cannot access user profiles or auth endpoints
- **Audit Trail**: All actions logged with service name
- **Long-lived Tokens**: Expire after 365 days
- **Revocable**: Generate new token to revoke old ones

### Token Usage

```python
# Correct usage
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}
```

### Token Security Best Practices

- ✅ Store in environment variables
- ✅ Never commit to source control
- ✅ Rotate periodically (yearly recommended)
- ✅ Use separate tokens per environment (prod/local)
- ❌ Never hardcode in source code
- ❌ Never share tokens between services

## 🧪 Testing Integration

### 1. Health Check (No Auth)

```bash
# Basic health
curl https://missingtable.com/health

# Expected: {"status": "healthy", "version": "2.0.0"}

# Full health with database status
curl https://missingtable.com/health/full
```

### 2. Test Authentication

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://missingtable.com/api/matches

# Should return 200 with match data (not 401)
```

### 3. Test Async Submission

```bash
# Submit test match
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://missingtable.com/api/matches/submit \
     -d '{
       "home_team": "IFA",
       "away_team": "NEFC",
       "match_date": "2025-10-15T14:00:00Z",
       "season": "2025-26",
       "age_group": "U14",
       "division": "Northeast",
       "match_status": "scheduled",
       "match_type": "League",
       "external_match_id": "test-123"
     }'

# Get task_id from response, then check status
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://missingtable.com/api/matches/task/TASK_ID
```

### 4. Real Scraper Test

```bash
# Small test (today only, limit 5)
cd match-scraper
python -m src.cli.main scrape --start 0 --end 0 -a U14 -d Northeast --limit 5

# Broader test (last week to next week)
python -m src.cli.main scrape --start 7 --end 7 -a U14 -d Northeast
```

## 📊 Monitoring & Troubleshooting

### Check Celery Workers

```bash
# List workers in M4 Mac K3s (rancher-desktop context)
kubectl get pods -n match-scraper -l app=missing-table-worker

# Check worker logs
kubectl logs -n match-scraper -l environment=prod --tail=50
```

### Check Task Queue

```bash
# Port-forward to RabbitMQ management UI
kubectl port-forward -n messaging svc/messaging-rabbitmq 15672:15672

# Access UI at http://localhost:15672
# Default credentials: guest/guest
```

### When ingest drops matches

**A green scraper report is not proof that matches landed.** The scraper's
report counts errors from the RabbitMQ *publish*, and publishing succeeds
whether or not the backend can resolve the names. Team and division
resolution happens later, in a Celery worker. Before SB-829/SB-831 a run
where every name was unknown reported `1432 found, 1432 submitted, 0 errors`
and landed nothing.

Two things now make that visible:

1. **`ingest_failures`** — one row per distinct unresolved name, with the
   number of matches it cost. Not one row per dropped match: seven bad
   spellings read as seven problems, not four hundred.
2. **A Telegram alert** on each newly-seen name, sent to
   `MT_ADMIN_TELEGRAM_CHAT_ID`, capped at `MT_INGEST_ALERT_MAX_PER_HOUR`
   (default 10) so a new season does not turn the channel into a log tail.
   Past the cap names are still recorded; one message points at the API.

The scraper reads the same rows at end of run and folds them into its own
report, so `submitted` and `rejected by MT` appear side by side.

```bash
# What ingest could not resolve (admin or service-account token)
curl -H "Authorization: Bearer $TOKEN" \
  "$API/api/admin/ingest-failures?since=2026-09-05T00:00:00Z"
```

### Re-scraping corrects a wrongly-filed match

A re-scrape compares competition and division as well as teams, scores, status
and kickoff. Before SB-847 it did not: three clean re-submits of the 68 Flex
fixtures were accepted, found each match by `external_match_id`, recognised
nothing as changed, and logged `Match unchanged`. The rows could only be fixed
by writing to the database directly.

A correction is logged by name rather than by id, so a competition move is
visible in the worker log:

```
Match 4060 match_type corrected: League → Flex
```

**Matches somebody entered by hand are exempt.** The correction is gated on
`matches.source`: the feed re-files what it owns, and a friendly deliberately
recorded against a league fixture's external id keeps its competition. Scores
and status are *not* gated by source — scraped data still wins on results —
except on a score-locked row (below). Adopting a manual match (populating its
`match_id`) sets `source = 'match-scraper'`, after which the feed owns its
filing too.

### A person's result against the feed (SB-1787)

Two cases are recorded in `ingest_failures` rather than only logged, one row
per match per kind (`raw_name` is `match <id>`, `sample` says what differed,
`match_count` how many messages said it). The row is keyed on kind and match
alone — `league` is null and `source` is always `mt-worker` — so a second
sender or league spelling adds to the same row instead of opening another. They are not dropped matches, so
they are **left out of `/api/admin/ingest-failures` by default** — match-scraper
sums `match_count` over that list as "rejected by MT", and its report stays
right without any change there. List them on their own:

```bash
mt ingest failures --conflicts
curl -H "Authorization: Bearer $TOKEN" \
  "$API/api/admin/ingest-failures?kind=score_locked,scraped_overrode_manual"
```

(`include_conflicts=true` returns every kind; the mt-mcp `list_ingest_failures`
tool takes `conflicts=true`.) Neither kind closes by itself — close one with
`mt ingest resolve <id>` once someone has looked. A closed row stays closed
while the feed keeps sending the same thing; only a different detail (the
feed's score moved again) reopens it.

| Kind | When | What the worker does |
|------|------|----------------------|
| `score_locked` | the row has `score_locked = true` and the message's score, shootout, status or home/away differs | **holds** all four; date, kickoff and filing still follow the feed. Recorded after the message is processed, so an autoretry does not count it twice |
| `scraped_overrode_manual` | the row was a person's before this message (`source` not in `FEED_SOURCES`, read before adoption) and the feed's score or shootout replaces a different, non-empty one | writes the feed's score (rule 5) and records what it replaced |

Home/away is held with the score on a locked row: swapping the teams under a
held 3-1 would turn it into the other side's win. A feed that only has the
sides the other way round is compared in MT's orientation, so a locked 2-1
sent as a swapped 1-2 is recorded as a home/away disagreement, not a score
one. Filling a score that was empty replaces nothing and is not recorded.

**`score_locked` is SQL-only until SB-1794** — there is no UI or endpoint to
set it; today it is set in the database by hand.

A status counts as a disagreement only when the feed also carries a score:
its `scheduled`/`tbd` for a locked match is what it says before it has a
result, not a claim about one. A locked row keeps its home side, so its
kickoff is read in that side's club timezone even when the feed has the
sides swapped.

**Known gaps in "a person's score".** The signal is the row's `source`, not
`updated_by`: the legacy sync endpoint stamps `updated_by` for the scraper's
own service account, and any edit (a kickoff time) sets it for good. So:

- A person who edits the score of a **scraped** row through an edit endpoint
  is not distinguishable from the feed, and a later feed score over it is not
  recorded. That needs a provenance column for the score itself.
- Adoption re-stamps a hand-entered row as `match-scraper`. The adopting
  message is compared against the person's score; if it carried no score,
  nothing is kept, and a later feed score over the person's is not recorded.

There is still no void path: a `postponed` message never moves a `completed`
or `forfeit` row (SB-1136).

> **Deploy order:** apply `20261126120000_ingest_failures_conflict_kinds.sql`
> (`./scripts/db_tools.sh migrate prod`) **before** the worker image with this
> code is deployed. Until it is applied the record call fails the `kind`
> CHECK and is only logged — the match is still processed as described, but
> every conflict in that window is silently lost.

### Reconcile read: `GET /api/agent/season-matches`

match-scraper's `reconcile` compares past MT matches with the official feed and
resends what differs through the normal queue. It reads MT one page at a time
(admin, or a service account with `manage_matches` — not team or club
managers, unlike the other `/api/agent/*` reads):

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$API/api/agent/season-matches?season_id=5&start_date=2026-09-01&end_date=2026-11-30&league_ids=1,2&page=0&page_size=500"
```

| Param | |
|-------|-|
| `season_id` | required |
| `start_date`, `end_date` | optional, `YYYY-MM-DD`, inclusive |
| `league_ids` | optional, comma-separated; keeps matches whose division is in those leagues, which leaves out tournament matches |
| `page` | 0-based, default 0 |
| `page_size` | default 500, max 1000 |

**Page contract:** rows are ordered by `(match_date, id)`; page `n` starts at
row `n * page_size`. Ask for pages 0, 1, 2… and stop at the first page whose
`matches` is **empty** — a short page is not proof of the last one. **Read
every page before sending any change**: a correction that re-dates a match
moves it between pages, so sending while paging can skip or repeat rows. A
database error is a 500, never an empty page; a malformed date is a 422.

Each row: `id`, `match_id` (external), `match_date`, `match_status`,
`home_team_id`/`home_team_name`, `away_team_id`/`away_team_name`,
`home_score`/`away_score`, `home_penalty_score`/`away_penalty_score`,
`division_id`, `league_id`, `match_type`, `source`, `entered_by_person`
(`source` is not one the feed writes — the worker's test; `updated_by` is not
returned) and `score_locked`. Every
status is returned, `cancelled` included; an unplayed match's scores are
`null`, not `0`.

### Tournament matches

A message that carries `tournament_id` is a **tournament message** (SB-1747).
Its match is filed on the tournament — `matches.tournament_id` set,
`division_id` null — instead of in a league division. Everything else about
the message is unchanged, and every field below is optional and additive: a
league message does not send them and is processed exactly as before.

These are fields on the queue message (`process_match_data`). The HTTP submit
endpoint does not accept them.

| Field | Type | Meaning |
|-------|------|---------|
| `tournament_id` | integer ≥ 1 | `tournaments.id`. Its presence is what makes the message a tournament message |
| `competition` | string \| null | The feed's own competition name, as sent — `HD Group Play`, `AD Showcase`, `GA Cup Qualifier` |
| `tournament_group` | string \| null | The feed's own group label, as sent — `A`. **Not** the stored value; see below |
| `tournament_round` | string \| null | A round key — `group_stage`, `showcase`, `placement_final`, … |
| `tournament_round_order` | integer ≥ 0 \| null | Position within the round |

On a tournament message, three existing fields are constrained:

| Field | Rule |
|-------|------|
| `external_match_id` | **Required.** It is what a rescrape upserts on |
| `match_type` | Must be `Tournament` (any case). The id is looked up by name |
| `division` | Must be omitted or null |

`league` stays optional, but on a tournament message it does more than it does
on a league message: it names the **side** the teams are on, and a team name
is resolved on that side or not at all — see
[Which team a name means](#which-team-a-name-means). When sent it must be the
name of a league MT has (`Homegrown`, `Academy`, `Flex`); anything else drops
the match as an unknown league. `home_penalty_score` /
`away_penalty_score`, `source`, `age_group`, `season` and the kickoff fields
behave as they always have. The full contract is
[`match-message-schema.json`](match-message-schema.json).

#### Which team a name means

A tournament such as MLS NEXT Fest puts the Homegrown Division (`HD …`
competitions) and the Academy Division (`AD …`) in one event, and many clubs
field a team on each side **under the same name**. On a league message an
exact `teams.name` hit is taken whatever `league` says — the league only
scopes aliases — which on a tournament message would file an Academy fixture
on the Homegrown team's history, silently. So a tournament message resolves
its two team names differently (SB-1748,
`TeamDAO.resolve_tournament_team`), in this order:

0. **The `league` itself.** If the message sends one and MT has no league by
   that name, the message fails here and no team is looked up — see
   [An unknown league](#an-unknown-league).
1. **An alias scoped to the message's `league`** (`team_aliases.league_id`,
   SB-1652). A deliberate statement about that league: trusted as it stands.
2. **The exact team name** — every team with that name, not the first one.
3. **An alias with no league.** An alias scoped to a *different* league does
   not apply.
4. **The side guard**, on whichever of 2 and 3 found anything first.

Matching is exact apart from letter case and whitespace. Nothing is fuzzy,
nothing is inferred from a club's other teams, and nothing is created. The
name is compared as text, never as a pattern: `%` and `_` in a feed name match
only themselves, both against team names and against aliases, and a name the
database cannot be asked about at all (one ending in a backslash, before this
was escaped) is an unknown team, not a retried error. League messages are not
changed by this; their alias lookup is as it was.

A name that is both one team's exact name and a league-agnostic alias of
another resolves to the team that owns the name — step 2 found something, so
step 3 is not consulted. If that team is on the other side the message fails
as `wrong side`; it does not fall through to the alias. A league-scoped alias
(step 1) is the way to say what the name means on one side.

**A team's side** at the message's age group is the set of leagues of the
divisions it is registered in at that age (`team_mappings`), a child league
counted as its parent (`leagues.parent_league_id`: Flex is Homegrown). A team
with no registration at that age is judged by its registrations at every age
plus `teams.league_id`, folded the same way. `teams.league_id` alone is not
the test: Homegrown clubs carry Flex there and MLS academies carry nothing.

**The guard** then keeps the candidates whose side includes the message's
`league` (itself folded to its parent) — and of those, only the ones that are
**cleanly** on it. A team registered on the hinted side *and* another at the
message's age group (an Academy division and a Homegrown one, both at U14) is
not a clean match: its registrations cannot say which side it is, and taking
it for an Academy message is exactly the Academy-fixture-on-a-Homegrown-team
fault. A handful of production teams are mapped that way, left over from old
mis-filing.

| `league` | Candidates left | Result |
|----------|-----------------|--------|
| sent | exactly one cleanly on that side | that team — even if a both-sides team shares the name |
| sent | more than one cleanly on that side | fails — `ambiguous: team ids 7, 9` |
| sent | none cleanly on it, one or more on both sides | fails — `ambiguous: team 17 is registered as both Academy and Homegrown at this age group` |
| sent | none | fails — `wrong side: exists as Homegrown` |
| not sent | exactly one candidate | that team (a both-sides team included: there is no hint to contradict) |
| not sent | more than one candidate | fails — `ambiguous: team ids 7, 9` |

"Both sides" is judged at the message's age group only. A team with no
registration at that age is judged by its registrations at every other age
plus `teams.league_id`; if those span both sides it still answers either
hint, as it did.

A team with no registrations and no `teams.league_id` has no side: it resolves
only for a message that sends no `league`, and otherwise fails as
`wrong side: team has no league or division registration`.

A failure is a `team` row in `ingest_failures` like any other unknown name —
recorded once per name **and league**, counted, not retried — with the reason
appended to its `sample` in square brackets:

- **`wrong side: exists as <league>`** — the name is a team, but only on the
  other side. The team on this side does not exist yet, or is not registered
  at any age group, or goes by another name and needs a league-scoped alias.
- **`wrong side: team has no league or division registration`** — the name is
  a team that is registered nowhere, so nothing says which side it is on.
- **`ambiguous: team ids …`** — more than one team on this side (or, with no
  `league`, more than one team at all) has that name. The ids are the
  candidates; MT picks none of them.
- **`ambiguous: team N is registered as both Academy and Homegrown at this age
  group`** — the only team with that name on this side is mapped into both at
  the message's age group. Remove the mapping that is wrong
  (`mt team mapping list` shows them) and the name resolves.

Ingest never creates the missing team. Before a large event, `mt ingest plan`
puts the event's whole team list through this same resolver, reports what
would fail, and proposes the aliases and teams that fix it for a person to
review and `mt ingest apply` (SB-1763):
[Planning a tournament's teams](tournament-team-plan.md).

#### An unknown league

A tournament message whose `league` is not the name of a league MT has —
`HD`, `Homegrown Division`, a typo — is **one** failure for that string, kind
`league`, with the string as its `raw_name` and no `league` of its own. It is
recorded once and counted, not retried, and no team is looked up. The name is
compared whole, without case or padding; it is never a pattern and never a
nearest match. It fails closed: the message is dropped, not resolved as if no
`league` had been sent.

Before this, the wrong string reached the side guard and every team in the
event failed as `wrong side: exists as Homegrown` — one misleading row per
team (about 1,350 at a Fest) for one mistake at the sender.

A league message is not affected. An unknown `league` there is still a logged
warning and unscoped lookups, exactly as before.

A league message is untouched by all of this: it still resolves through
`resolve_team_by_name`, with the same calls in the same order.

**Closing a failure is per league too.** When a name resolves, its open
failure row closes itself. For a tournament message only the row for the
message's `league` is closed (`resolve_ingest_failures_by_league`), so a
Homegrown success does not close the Academy row for the same name — which
would reopen on the next Academy failure and alert again.

> **Deploy note.** That function is a migration
> (`20261124120000_ingest_failures_resolve_by_league.sql`), applied with
> `./scripts/db_tools.sh migrate prod`. Until it is, tournament team failure
> rows are simply not auto-closed — the worker logs once that the function is
> missing and leaves them open rather than closing the wrong side's. A worker
> that has been told the function is missing does not call it again for ten
> minutes, rather than twice per tournament message, so closing starts within
> ten minutes of the migration landing, without a restart. Resolution itself
> does not depend on the migration.

**What it costs.** The side guard needs the `leagues` table; each worker reads
it once and keeps it for ten minutes, so a league created or renamed is seen
within that. A hinted name is then two queries (aliases, teams), three when it
is reached only through a league-agnostic alias.

#### What is stored in `tournament_group`

`competition` and `tournament_group` are raw feed values. The stored
`matches.tournament_group` is one namespaced string built from them, in the
[frozen group format](../features/TOURNAMENTS.md#group-format), by
`stored_group` in `backend/celery_tasks/tournament_filing.py`:

1. **Division** is `HD` or `AD` when the competition's first word is exactly
   that (any case, stored upper-case). Otherwise there is no division.
2. **`group_stage`** — the group label, namespaced by the division, or by the
   whole competition when it has none.
3. **Any other round** — the feed's group label is not a group there
   (`Playoffs`), so the competition is what the match is filed under: the
   division plus the rest of the competition name, or the competition whole.
4. **No competition at all** — the raw group label, unchanged.
5. **Not enough to say** — no stored value is produced, and nothing is written
   over the one already there, when the round is missing, when a `group_stage`
   message has no group label, or when any other round has neither a
   competition nor a group. Composing from what is left would yield a
   different string (`HD` for `HD · A`), and bracket follows key on the
   stored one.

Runs of whitespace inside `competition` are collapsed to a single space first,
so `HD  Group  Play` and `HD Group Play` store the same bytes. Letter case is
left as sent, apart from the `HD`/`AD` token.

| `competition` | `tournament_group` | `tournament_round` | Stored |
|---------------|--------------------|--------------------|--------|
| `HD Group Play` | `A` | `group_stage` | `HD · A` |
| `AD Group Play` | `A` | `group_stage` | `AD · A` |
| `GA Cup Qualifier` | `NEXT Pro` | `group_stage` | `GA Cup Qualifier · NEXT Pro` |
| *(none)* | `Bracket A` | `group_stage` | `Bracket A` |
| `HD Showcase` | *(anything)* | `showcase` | `HD · Showcase` |
| `HD Group Play` | `Playoffs` | `placement_final` | `HD · Group Play` |
| `GA Cup Qualifier` | *(anything)* | `final` | `GA Cup Qualifier` |
| `Pro Player Pathway` | *(none)* | `showcase` | `Pro Player Pathway` |
| `HD Group Play` | *(none)* | `group_stage` | *(nothing — stored value kept)* |
| `HD Group Play` | `A` | *(none)* | *(nothing — stored value kept)* |

Empty and whitespace-only strings are treated as absent. A value the frozen
format rejects — a namespace containing ` · `, or a bare label containing it —
drops the match as `invalid` rather than being stored altered.

#### The upsert rule

A tournament match is upserted on its source match id
(`external_match_id` → `matches.match_id`, which is unique):

- **Found by source id** → the same row is updated. Scores, the shootout and
  status follow the rules they always have. A rescrape with nothing new is
  `skipped` and writes nothing.
- **Not found** → a teams-and-date lookup, to adopt a match somebody entered
  by hand. A hit is adopted only when it is **on the same tournament** and has
  no source id: it takes the feed's id and `source = 'match-scraper'`, and is
  not duplicated. Any other hit is left alone and this message creates its own
  row — a league or friendly match between the same teams that day, a match on
  another tournament, or one that already has a *different* source id (another
  fixture between the same teams, routine at a tournament). These checks are
  made for tournament messages only; a league message takes the teams-and-date
  hit exactly as it did before.
- **An adopted row is only filled in.** On the message that adopts it, the
  tournament columns are written where the row has none; a group or round
  somebody typed (`Group A`) stays. This holds for the adopting message only:
  the row is the feed's from then on, and a later rescrape re-files it like
  any other.
- **A row is never moved between competitions.** A row found by source id that
  is in a league division, or on a different tournament, is not re-filed onto
  this one. The message is dropped as `invalid` and the row is left untouched.
  A row with no division and no tournament is filed.
- **A null never clears.** A rescrape that omits the group, round or order
  leaves the stored value in place. Nor does a partial one re-file: see rule 5
  above, and a stored namespaced group (`HD · A`) is never replaced by one
  without a namespace (`A`).
- **A hand-entered row keeps its filing.** Tournament columns are re-filed
  only on rows the feed owns: `matches.source` is `match-scraper` or
  `match-scraper-agent` (the live sender), or empty. Scores still land.
  Competition and division re-filing (above) is narrower — `match-scraper`
  only — so a row the agent created has its tournament columns corrected by a
  rescrape but not its `match_type_id` or `division_id`.
- **User data is never touched.** Ingest writes columns on `matches` only.
  Goals and other `match_events` a manager logged survive every rescrape, and
  a scraped score that disagrees with them is left disagreeing.

A created row carries `source` from the message (default `match-scraper`), so
provenance stays queryable.

Updates to a tournament match are written through
`MatchDAO.update_ingested_tournament_match`, which clears the tournament and
match caches **of the process doing the write** — and only if that process has
the cache switched on. Clearing is a no-op unless `CACHE_ENABLED=true` and
`REDIS_URL` points at a Redis it can reach (`dao/base_dao.py`).

**In production that is not the ingest worker.** The API has
`CACHE_ENABLED: "true"` (`helm/missing-table/values-prod.yaml`) and a
`REDIS_URL` for the Redis in its own cluster
(`helm/missing-table/templates/backend.yaml`). The worker
(`k3s/worker/deployment-prod.yaml`) sets neither, and runs in a different
cluster from that Redis. So a match the worker creates, or a score it writes,
does not clear the API's cache.

**Tournament pages are bounded by a TTL instead** (SB-1756). The tournament
reads that carry scores or match counts — the list with its `match_count`,
the admin list, the detail call, the match pages and their facets — are
cached for 60 seconds (`TOURNAMENT_SCORE_CACHE_TTL` in
`dao/tournament_dao.py`), so the Tournaments page shows a scraped score or a
newly created match within about a minute, with no signal from the worker.

That is all it covers. League standings (`MatchDAO.get_standings`) and
single-match detail (`MatchDAO.get_match_by_id`) are still cached for 24
hours, and still stale after a worker write until an API-side write or a
deploy's cache flush clears them.

#### What drops a tournament match

Each is recorded once in `ingest_failures` (kind `invalid` unless noted), with
a count, and is not retried:

| Problem | `raw_name` |
|---------|------------|
| `tournament_id` does not exist | `unknown tournament_id 99` |
| The row with this source id is in a league division | `tournament_id 12 sent for a match already filed on a league division` |
| The row with this source id is on another tournament | `tournament_id 12 sent for a match already filed on tournament 11` |
| Age group not in `age_groups` | `unknown age group 'U99' on a tournament match` |
| A tournament field with no `tournament_id` | `tournament_group requires tournament_id` |
| Missing `external_match_id`, wrong `match_type`, a `division`, a malformed round key, a wrong type | the rule that failed |
| A `league` that is not a league MT has (kind `league`) | the `league` string — see [An unknown league](#an-unknown-league) |
| Unknown team name (kind `team`) | the name, as for a league message |
| Team name that exists only on the other side, or matches more than one team (kind `team`) | the name; the reason is in `sample` — see [Which team a name means](#which-team-a-name-means) |

An unknown age group is a failure **only** for tournament messages. A league
message still falls back to age group id 1, as before.

A round key outside the set MT knows (`VALID_ROUNDS`) is *not* a failure: it
is validated for shape (lowercase snake_case, at most 40 characters), filed,
and logged with a warning, so a feed that grows a round does not lose matches.

Teams are never created by ingest. A tournament brings clubs MT has not seen;
until they exist as teams or aliases, their matches are dropped and reported.
Ingest registers no `team_mappings` row for a tournament match — there is no
division to register.

### Ingest registers the age group

A team's `age_groups` come entirely from `team_mappings`, and every age-group
team picker filters on it. Until SB-852 nothing on the ingest path wrote that
table, so a team the scraper had been filing matches for all season did not
exist at that age group as far as the product was concerned — NEFC had 44 U15
matches and an empty U15 team picker.

Creating a match now registers both teams for `(age_group, division)`.
Deliberately narrow:

* **The team's own league only.** A Homegrown team's Flex matches carry the
  Flex bracket's `division_id`. Writing that would give the team two divisions
  at one age group. Teams *can* now hold several (SB-1468: the API returns
  `divisions_by_age_group_all`, home league first), but ingest still should not
  invent registrations. Flex participation is already expressed by the matches, and Flex
  standings read matches directly (SB-835).
* **Nothing without a division.** Friendlies and tournament fixtures carry
  none, so there is no registration to express.
* **A registration failure never fails the match.** The match landing matters
  more than its registration row; the failure is logged.

To correct one by hand:

```bash
mt team mapping list "NEFC"
mt team mapping add "NEFC" --age U16 --division Northeast
```

### Closing a failure row

A row closes **itself** when the same name later resolves — add the alias and
the next successful match for that name clears the alert. That covers the case
where the fix is to teach MT about the name.

It cannot cover the other one. When the fix is to stop *sending* the bad name,
that string is never submitted again, nothing triggers the resolve, and the row
would be reported forever as a problem that no longer exists (SB-845). Close
those by hand:

```bash
mt ingest failures                       # what is open, and what each cost
mt ingest resolve 1 --note "fixed at the sender"
```

```bash
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"note": "fixed at the sender"}' \
  "$API/api/admin/ingest-failures/1"
```

Admin only, not service accounts: this is a person deciding a name is no longer
a problem. **Resolving never deletes** — `resolved_at`, `resolved_by` and
`resolution_note` are stamped on the row, because the history of which names
were wrong and when is most of what makes the table worth having.

### `stale` is a hint, not a verdict

Every row in the list response carries `stale`: true when it has not been seen
for `stale_after_days` (`MT_INGEST_STALE_AFTER_DAYS`, default 7). The response
also carries `stale_count` and `stale_after_days` so a client knows the rule it
is being told about.

Nothing auto-closes on that basis. A name fixed at the sender and a name that
simply was not scraped this week look identical from here, and closing the
second would lose a real problem. The flag exists so a run report can
de-emphasise a row rather than keep crying wolf about it; deciding stays with a
person.

An unresolved name is **permanent** — it raises `UnresolvedNameError`, which
is excluded from the task's autoretry. Waiting will not make an unknown team
known, and retrying three times with backoff only delays the alert.

### Common Issues

**Issue: "Team not found: TeamName"**

The name in the feed does not match `teams.name` **or** any row in
`team_aliases`. Resolution is scoped to the feed's league, so an alias
registered for a different league does not apply.

The fix is usually an alias rather than a new team — the team almost always
already exists under a different spelling:

```bash
mt team alias add "IFA" "Intercontinental Football Academy of New England"
```

Adding the alias closes the `ingest_failures` row on the next successful
match for that name; no manual cleanup needed. Check first with
`GET /api/teams` or `mt search`.

**Issue: "Match type not found: CompetitionName"**

The feed's `match_type` must name a row in `match_types`. Until SB-847 it was
not read at all — every scraped match was created as `match_type_id` 1, which
is how 68 MLS NEXT Flex fixtures went into production filed as League.

An unknown competition is now recorded in `ingest_failures` with
`kind = 'match_type'` and fails the match, for the same reason an unknown
division does: a plausible default looks correct, so nobody goes looking. Seed
the competition (and its `counts_for_qualification` / `display_order` values)
before loading it.

**Issue: "Division not found: DivisionName"**

Division names are unique **per league**, not globally — the 2026-2027 feeds
put `Florida`, `Frontier`, `Northwest` and `Southeast` in both Homegrown and
MLS NEXT Flex. Either the division is genuinely missing, or the feed's league
name does not map to a league in `leagues` and the lookup could not be
scoped.

This used to write `division_id = NULL`, which put the match in the database
and in no standings table. It now fails instead.

**Issue: Task stuck in PENDING**
- Check Celery workers are running
- Check RabbitMQ is accessible
- View worker logs for errors

**Issue: Duplicate matches**
- Set `external_match_id` to unique value
- Database constraint prevents duplicates with same external_match_id

**Issue: Authentication failed**
- Verify token is valid (not expired)
- Check `Authorization: Bearer TOKEN` header format
- Test with health check endpoint first

## 🔄 Workflow Examples

### Daily Schedule Import

```python
async def import_daily_schedule():
    client = MissingTableClient()

    # 1. Scrape matches from MLS Next
    matches = await scrape_mls_matches()

    # 2. Submit all matches for async processing
    task_ids = []
    for match in matches:
        result = await client.submit_match_async({
            "home_team": match.home_team,
            "away_team": match.away_team,
            "match_date": match.match_datetime.isoformat(),
            "season": calculate_season(match.match_datetime),
            "age_group": match.age_group,
            "division": match.division,
            "match_status": match.match_status,
            "match_type": "League",
            "external_match_id": match.match_id
        })
        task_ids.append(result["task_id"])

    # 3. Optionally wait for completion
    print(f"Submitted {len(task_ids)} matches for processing")
```

### Score Updates

```python
async def update_scores():
    client = MissingTableClient()

    # 1. Scrape updated scores
    completed_matches = await scrape_completed_matches()

    # 2. Submit updates (same endpoint, uses external_match_id for deduplication)
    for match in completed_matches:
        await client.submit_match_async({
            "home_team": match.home_team,
            "away_team": match.away_team,
            "match_date": match.match_datetime.isoformat(),
            "season": match.season,
            "age_group": match.age_group,
            "division": match.division,
            "match_status": "played",
            "match_type": "League",
            "home_score": match.home_score,
            "away_score": match.away_score,
            "external_match_id": match.match_id  # Same ID = update
        })
```

## 📝 Data Model

### Async API Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `home_team` | string | Yes | Home team name |
| `away_team` | string | Yes | Away team name |
| `match_date` | string (ISO 8601) | Yes | Match date/time |
| `season` | string | Yes | Season (e.g., "2025-26") |
| `age_group` | string | Yes | Age group (U13-U19) |
| `division` | string | Yes | Division name |
| `match_status` | string | Yes | "scheduled" or "played" |
| `match_type` | string | Yes | A `match_types.name`: "League", "Flex", "Tournament", "Friendly". Unknown names are rejected, not defaulted |
| `home_score` | integer | No | Home score (null for scheduled) |
| `away_score` | integer | No | Away score (null for scheduled) |
| `external_match_id` | string | No | External ID for deduplication |
| `location` | string | No | Match location/venue |

### Match Status Values

- `scheduled` - Match not yet played
- `played` - Match completed with final scores

### Season Format

Seasons follow MLS Next format (August to July):
- `2025-26` - Aug 2025 to Jul 2026
- `2024-25` - Aug 2024 to Jul 2025

## 🔧 Database

The scraper pipeline writes to **prod Supabase** (missingtable.com). There is no dev Supabase — only prod and local.

- **Prod**: Workers in M4 Mac K3s write to `ppgxasqgqbnauvxozmjw.supabase.co`
- **Local**: Local workers write to `localhost:55321`
- **Backup**: Use `./scripts/db_tools.sh backup` before major operations
- **Restore**: Use `./scripts/db_tools.sh restore` if needed

## 📞 Support & Resources

- **API Documentation**: https://api.missingtable.com/docs
- **Match-Scraper Repo**: Check README for latest CLI options
- **Database Tools**: `./scripts/db_tools.sh --help`
- **Backend Logs**: `kubectl logs -n missing-table -l app=backend`
- **Worker Logs**: `kubectl logs -n match-scraper -l environment=prod`

## 🎯 Migration Guide: Sync → Async

If you're currently using the sync API, here's how to migrate:

### Before (Sync API)
```python
# 1. Look up entity IDs
teams = await client.list_teams()
home_team_id = find_team_id(teams, "IFA")
away_team_id = find_team_id(teams, "NEFC")

seasons = await client.list_seasons()
season_id = find_season_id(seasons, "2025-26")

# ... more lookups ...

# 2. Submit match
await client.create_match({
    "home_team_id": home_team_id,
    "away_team_id": away_team_id,
    "season_id": season_id,
    # ... all IDs required
})
```

### After (Async API)
```python
# Just submit with names - backend handles lookups
result = await client.submit_match_async({
    "home_team": "IFA",
    "away_team": "NEFC",
    "season": "2025-26",
    "age_group": "U14",
    "division": "Northeast",
    # ... use names/strings instead of IDs
})
```

**Key Changes:**
- ✅ No entity ID lookups needed
- ✅ No team cache preloading
- ✅ Simpler code, fewer API calls
- ✅ Better error messages from backend
- ✅ Automatic retries on transient failures

---

## 🔮 Future: Direct RabbitMQ Integration

The next evolution removes the HTTP API dependency for match submission. See the detailed implementation plan:

**Documentation:**
- [Implementation Plan](../NEXT_SESSION_PLAN.md) - Step-by-step guide for direct queue integration
- [Message Contract](./match-message-schema.json) - JSON Schema for match messages

**Benefits:**
- ✅ **Resilience** - Scraper continues working even if backend API is down
- ✅ **Decoupling** - No HTTP API dependency for match submissions
- ✅ **Simplicity** - Direct message passing, no REST overhead
- ✅ **Performance** - Faster submission, no HTTP round-trips

**Architecture Pattern:**
- **Producer** (match-scraper) - Sends JSON messages to RabbitMQ queue
- **Broker** (RabbitMQ) - Holds messages reliably
- **Consumer** (celery workers) - Processes messages from queue
- **Contract** (JSON Schema) - Single source of truth, no code sharing

**Key Insight:** The two repos will NOT share Python code. Instead, they share a JSON Schema contract and each has its own Pydantic model (intentional duplication to avoid dependency hell). Contract tests ensure the models stay in sync.

---

**Last Updated**: 2025-10-13
**API Version**: 2.0.0 (3.0 planned with direct queue integration)
**Match-Scraper Compatible**: Yes (async API), direct queue integration planned
