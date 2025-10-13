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
uv run python create_service_account_token.py --service-name match-scraper --permissions manage_matches

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
# In match-scraper .env.dev file
MISSING_TABLE_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
MISSING_TABLE_API_BASE_URL=https://dev.missingtable.com

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
Match-Scraper → POST /api/matches/submit → RabbitMQ Queue
                                              ↓
                                         Celery Workers (2+ replicas)
                                              ↓
                                    Entity Resolution + Database
```

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
        base_url="https://dev.missingtable.com",
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
curl https://dev.missingtable.com/health

# 2. Submit match for async processing
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://dev.missingtable.com/api/matches/submit \
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
     https://dev.missingtable.com/api/matches/task/TASK_ID_HERE
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
- ✅ Use separate tokens per environment (dev/prod)
- ❌ Never hardcode in source code
- ❌ Never share tokens between services

## 🧪 Testing Integration

### 1. Health Check (No Auth)

```bash
# Basic health
curl https://dev.missingtable.com/health

# Expected: {"status": "healthy", "version": "2.0.0"}

# Full health with database status
curl https://dev.missingtable.com/health/full
```

### 2. Test Authentication

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://dev.missingtable.com/api/matches

# Should return 200 with match data (not 401)
```

### 3. Test Async Submission

```bash
# Submit test match
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST https://dev.missingtable.com/api/matches/submit \
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
     https://dev.missingtable.com/api/matches/task/TASK_ID
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
# List workers in GKE
kubectl get pods -n missing-table-dev | grep celery-worker

# Check worker logs
kubectl logs -n missing-table-dev deployment/missing-table-celery-worker
```

### Check Task Queue

```bash
# Port-forward to RabbitMQ management UI
kubectl port-forward -n messaging svc/messaging-rabbitmq 15672:15672

# Access UI at http://localhost:15672
# Default credentials: guest/guest
```

### Common Issues

**Issue: "Team not found: TeamName"**
- Verify team exists in database
- Check team name spelling matches exactly
- Query teams: `GET /api/teams`

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
| `match_type` | string | Yes | "League", "Friendly", "Tournament" |
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

## 🔧 Development Database

Match-scraper works against the development database:
- **Environment**: Use `dev` environment in GKE
- **Backup**: Use `./scripts/db_tools.sh backup` before major operations
- **Restore**: Use `./scripts/db_tools.sh restore` if needed

## 📞 Support & Resources

- **API Documentation**: https://dev.missingtable.com/docs
- **Match-Scraper Repo**: Check README for latest CLI options
- **Database Tools**: `./scripts/db_tools.sh --help`
- **Backend Logs**: `kubectl logs -n missing-table-dev deployment/missing-table-backend`
- **Worker Logs**: `kubectl logs -n missing-table-dev deployment/missing-table-celery-worker`

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
