# Match-Scraper Integration Guide

This guide explains how to integrate match-scraper with the Missing Table API using service account authentication.

## 🔐 Authentication Setup

### 1. Generate Service Account Token

```bash
# Generate a token for match-scraper with game management permissions
cd backend
python create_service_account_token.py --service-name match-scraper --permissions manage_games

# Example output:
# Service Account Token Generated Successfully!
#
# Service Name: match-scraper
# Permissions: manage_games
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

### Create New Games

```bash
POST /api/games
Authorization: Bearer {service_account_token}
Content-Type: application/json

{
  "game_date": "2024-03-15",
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 0,
  "away_score": 0,
  "season_id": 1,
  "age_group_id": 2,
  "game_type_id": 1,
  "division_id": 1
}
```

### Update Game Scores

```bash
PUT /api/games/{game_id}
Authorization: Bearer {service_account_token}
Content-Type: application/json

{
  "game_date": "2024-03-15",
  "home_team_id": 1,
  "away_team_id": 2,
  "home_score": 2,
  "away_score": 1,
  "season_id": 1,
  "age_group_id": 2,
  "game_type_id": 1,
  "division_id": 1
}
```

### Retrieve Existing Games

```bash
# Get all games with filtering
GET /api/games?season_id=1&age_group_id=2&team_id=1

# Get games for specific team
GET /api/games/team/1?season_id=1
```

## 📊 Data Model Reference

### EnhancedGame Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `game_date` | string | Yes | Game date in YYYY-MM-DD format |
| `home_team_id` | integer | Yes | ID of home team |
| `away_team_id` | integer | Yes | ID of away team |
| `home_score` | integer | Yes | Home team score (0 for scheduled games) |
| `away_score` | integer | Yes | Away team score (0 for scheduled games) |
| `season_id` | integer | Yes | Season identifier |
| `age_group_id` | integer | Yes | Age group (U13, U14, etc.) |
| `game_type_id` | integer | Yes | Game type (1=League, 2=Friendly, 3=Tournament) |
| `division_id` | integer | No | Division identifier |

### Reference Data IDs

You'll need to map your scraped data to these reference IDs:

```bash
# Get reference data
GET /api/teams          # Get team IDs
GET /api/seasons        # Get season IDs
GET /api/age-groups     # Get age group IDs
GET /api/game-types     # Get game type IDs (if available)
GET /api/divisions      # Get division IDs
```

## 🔄 Match-Scraper Workflow

### 1. Schedule Import
```python
import requests

headers = {
    "Authorization": f"Bearer {MISSING_TABLE_API_TOKEN}",
    "Content-Type": "application/json"
}

# Create scheduled games (scores = 0)
game_data = {
    "game_date": "2024-03-15",
    "home_team_id": home_team_mapping[home_team_name],
    "away_team_id": away_team_mapping[away_team_name],
    "home_score": 0,
    "away_score": 0,
    "season_id": current_season_id,
    "age_group_id": age_group_mapping[age_group],
    "game_type_id": 1,  # League game
    "division_id": division_mapping.get(division)
}

response = requests.post(
    f"{MISSING_TABLE_API_BASE_URL}/api/games",
    headers=headers,
    json=game_data
)
```

### 2. Score Updates
```python
# Update game with final scores
game_update = {
    "game_date": "2024-03-15",
    "home_team_id": 1,
    "away_team_id": 2,
    "home_score": 2,
    "away_score": 1,
    "season_id": current_season_id,
    "age_group_id": age_group_id,
    "game_type_id": 1,
    "division_id": division_id
}

response = requests.put(
    f"{MISSING_TABLE_API_BASE_URL}/api/games/{game_id}",
    headers=headers,
    json=game_update
)
```

## 🛡️ Security Features

### Service Account Permissions
- **Limited Scope**: Service accounts only have `manage_games` permission
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

# The API will identify this as a service account and allow game management
```

## 🧪 Testing Integration

### 1. Test Authentication
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/games

# Should return game data (not 401 Unauthorized)
```

### 2. Test Game Creation
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST http://localhost:8000/api/games \
     -d '{
       "game_date": "2024-03-15",
       "home_team_id": 1,
       "away_team_id": 2,
       "home_score": 0,
       "away_score": 0,
       "season_id": 1,
       "age_group_id": 2,
       "game_type_id": 1,
       "division_id": 1
     }'
```

### 3. Test Score Updates
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -X PUT http://localhost:8000/api/games/123 \
     -d '{
       "game_date": "2024-03-15",
       "home_team_id": 1,
       "away_team_id": 2,
       "home_score": 2,
       "away_score": 1,
       "season_id": 1,
       "age_group_id": 2,
       "game_type_id": 1,
       "division_id": 1
     }'
```

## 🔧 Development Database

Match-scraper will work against the **main development database** (`supabase/`):
- **Real Data**: ~502 records including 21 teams, 347 games
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
  "detail": "Service account requires 'manage_games' permission"
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
python backend/create_service_account_token.py --service-name match-scraper --permissions manage_games

# Update match-scraper environment
# Old tokens become invalid when new ones are generated with same service name
```

## 📞 Support

- **API Documentation**: http://localhost:8000/docs
- **Database Tools**: `./scripts/db_tools.sh --help`
- **Logs**: Check backend logs for authentication and API call details