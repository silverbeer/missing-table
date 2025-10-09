# Match-Scraper Integration Guide

This guide explains how to integrate match-scraper with the Missing Table API using service account authentication.

## 🔐 Authentication Setup

### 1. Generate Service Account Token

```bash
# Generate a token for match-scraper with match management permissions
cd backend
python create_service_account_token.py --service-name match-scraper --permissions manage_matches

# Example output:
# Service Account Token Generated Successfully!
#
# Service Name: match-scraper
# Permissions: manage_matches
# Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. Environment Configuration

Add the generated token to your match-scraper environment:

```bash
# In match-scraper .env file
MISSING_TABLE_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
MISSING_TABLE_API_BASE_URL=http://localhost:8000
```

## 🚀 API Endpoints for Match-Scraper

### Create New Matches

```bash
POST /api/matches
Authorization: Bearer {service_account_token}
Content-Type: application/json

{
  "match_date": "2024-03-15",
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

### Update Match Scores

```bash
PUT /api/matches/{match_id}
Authorization: Bearer {service_account_token}
Content-Type: application/json

{
  "match_date": "2024-03-15",
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 2,
  "away_score": 1,
  "season_id": 1,
  "age_group_id": 2,
  "match_type_id": 1,
  "division_id": 1
}
```

### Retrieve Existing Matches

```bash
# Get all matches with filtering
GET /api/matches?season_id=1&age_group_id=2&team_id=1

# Get matches for specific team
GET /api/matches/team/1?season_id=1
```

## 📊 Data Model Reference

### Match Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `match_date` | string | Yes | Match date in YYYY-MM-DD format |
| `home_team_id` | integer | Yes | ID of home team |
| `away_team_id` | integer | Yes | ID of away team |
| `home_score` | integer | Yes | Home team score (0 for scheduled matches) |
| `away_score` | integer | Yes | Away team score (0 for scheduled matches) |
| `season_id` | integer | Yes | Season identifier |
| `age_group_id` | integer | Yes | Age group (U13, U14, etc.) |
| `match_type_id` | integer | Yes | Match type (1=League, 2=Friendly, 3=Tournament, etc.) |
| `division_id` | integer | No | Division identifier |

### Reference Data IDs

You'll need to map your scraped data to these reference IDs:

```bash
# Get reference data
GET /api/teams          # Get team IDs
GET /api/seasons        # Get season IDs
GET /api/age-groups     # Get age group IDs
GET /api/match-types    # Get match type IDs
GET /api/divisions      # Get division IDs
```

## 🔄 Match-Scraper Workflow

### 1. Health Check (First Priority)
```python
import requests

# Always check backend health before proceeding
def check_backend_health():
    try:
        # Basic health check
        response = requests.get(f"{MISSING_TABLE_API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            if health_data.get("status") == "healthy":
                print(f"✅ Backend is healthy - version {health_data.get('version', 'unknown')}")
                return True

        print(f"❌ Backend health check failed: {response.status_code}")
        return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot reach backend: {e}")
        return False

# Optional: Full health check for detailed diagnostics
def full_health_check():
    try:
        response = requests.get(f"{MISSING_TABLE_API_BASE_URL}/health/full", timeout=15)
        if response.status_code == 200:
            health_data = response.json()
            print(f"📊 Full Health Check:")
            print(f"   Status: {health_data.get('status')}")
            print(f"   Database: {health_data.get('checks', {}).get('database', {}).get('status')}")
            print(f"   Reference Data: {health_data.get('checks', {}).get('reference_data', {}).get('status')}")
            return health_data.get("status") == "healthy"
    except Exception as e:
        print(f"❌ Full health check failed: {e}")
        return False

# Use in match-scraper startup
if not check_backend_health():
    print("Backend is not ready. Exiting match-scraper.")
    exit(1)
```

### 2. Schedule Import
```python
import requests

headers = {
    "Authorization": f"Bearer {MISSING_TABLE_API_TOKEN}",
    "Content-Type": "application/json"
}

# Create scheduled matches (scores = 0)
match_data = {
    "match_date": "2024-03-15",
    "home_team_id": home_team_mapping[home_team_name],
    "away_team_id": away_team_mapping[away_team_name],
    "home_score": 0,
    "away_score": 0,
    "season_id": current_season_id,
    "age_group_id": age_group_mapping[age_group],
    "match_type_id": 1,  # League match
    "division_id": division_mapping.get(division)
}

response = requests.post(
    f"{MISSING_TABLE_API_BASE_URL}/api/matches",
    headers=headers,
    json=match_data
)
```

### 3. Score Updates
```python
# Update match with final scores
match_update = {
    "match_date": "2024-03-15",
    "home_team_id": 1,
    "away_team_id": 2,
    "home_score": 2,
    "away_score": 1,
    "season_id": current_season_id,
    "age_group_id": age_group_id,
    "match_type_id": 1,
    "division_id": division_id
}

response = requests.put(
    f"{MISSING_TABLE_API_BASE_URL}/api/matches/{match_id}",
    headers=headers,
    json=match_update
)
```

## 🛡️ Security Features

### Service Account Permissions
- **Limited Scope**: Service accounts only have `manage_matches` permission
- **No User Data Access**: Cannot access user profiles, auth endpoints
- **Audit Trail**: All service account actions are logged with service name

### Token Security
- **Long-lived**: Tokens expire after 365 days by default
- **Revocable**: Generate new tokens to revoke old ones
- **Environment Variables**: Never hardcode tokens in source code

### Authentication Headers
```python
# Correct usage
headers = {"Authorization": f"Bearer {token}"}

# The API will identify this as a service account and allow match management
```

## 🧪 Testing Integration

### 1. Test Health Check (No Auth Required)
```bash
# Basic health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "2.0.0", "schema": "enhanced"}

# Full health check with database status
curl http://localhost:8000/health/full

# Expected response includes database and reference data status
```

### 2. Test Authentication
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/matches

# Should return match data (not 401 Unauthorized)
```

### 3. Test Match Creation
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST http://localhost:8000/api/matches \
     -d '{
       "match_date": "2024-03-15",
       "home_team_id": 1,
       "away_team_id": 2,
       "home_score": 0,
       "away_score": 0,
       "season_id": 1,
       "age_group_id": 2,
       "match_type_id": 1,
       "division_id": 1
     }'
```

### 4. Test Score Updates
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X PUT http://localhost:8000/api/matches/123 \
     -d '{
       "match_date": "2024-03-15",
       "home_team_id": 1,
       "away_team_id": 2,
       "home_score": 2,
       "away_score": 1,
       "season_id": 1,
       "age_group_id": 2,
       "match_type_id": 1,
       "division_id": 1
     }'
```

## 🔧 Development Database

Match-scraper will work against the **main development database** (`supabase/`):
- **Real Data**: ~502 records including 21 teams, 347 matches
- **Backup/Restore**: Use `./scripts/db_tools.sh backup` before major operations
- **Recovery**: Use `./scripts/db_tools.sh restore` to recover from backups

## 📝 Error Handling

### Common Response Codes
- **200**: Success
- **401**: Invalid or missing token
- **403**: Service account lacks required permissions
- **422**: Invalid data format
- **500**: Server error

### Example Error Responses
```json
// Missing authentication
{
  "detail": "Authentication required"
}

// Invalid permissions
{
  "detail": "Service account requires 'manage_matches' permission"
}

// Invalid data
{
  "detail": "Field 'home_team_id' is required"
}
```

## 🔄 Token Rotation

Generate new tokens periodically for security:

```bash
# Generate new token
python backend/create_service_account_token.py --service-name match-scraper --permissions manage_matches

# Update match-scraper environment
# Old tokens become invalid when new ones are generated with same service name
```

## 📞 Support

- **API Documentation**: http://localhost:8000/docs
- **Database Tools**: `./scripts/db_tools.sh --help`
- **Logs**: Check backend logs for authentication and API call details