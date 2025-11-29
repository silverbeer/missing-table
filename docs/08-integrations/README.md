# 🔌 Integrations Documentation

> **Audience**: Developers, integration engineers
> **Focus**: External API integrations
> **API Version**: 2.0

Documentation for integrating with external services and using the Missing Table API.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Match Scraper](match-scraper.md)** | MLS Next data scraper integration |
| **[API Usage](api-usage.md)** | Using the Missing Table API |
| **[Bruno Testing](bruno-testing.md)** | API testing with Bruno |

---

## 🎯 Integration Overview

### Available Integrations

**Data Sources**:
- MLS Next (via match-scraper)
- Manual data entry (Admin panel)

**API Consumers**:
- Frontend application
- Match-scraper service
- Third-party integrations

---

## 🔑 Authentication

### Service Account Tokens

```bash
# Generate token for external service
cd backend
uv run python scripts/utilities/create_service_account_token.py \
  --service-name match-scraper \
  --permissions manage_games

# Use token in API requests
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/games
```

### Token Permissions

- `manage_games`: Create, update, delete games
- `read_only`: Read all data
- `admin`: Full access (use sparingly)

---

## 📡 API Endpoints

### Public Endpoints (No Auth)

```bash
GET  /health                 # Health check
GET  /health/full           # Detailed health
GET  /api/teams             # List teams
GET  /api/games             # List games
GET  /api/standings         # Get standings
```

### Protected Endpoints (Auth Required)

```bash
POST   /api/games           # Create game
PUT    /api/games/:id       # Update game
DELETE /api/games/:id       # Delete game
POST   /api/teams           # Create team
```

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

---

## 🤖 Match Scraper Integration

### Overview

Automated MLS Next data collection using AI agents.

**Workflow**:
1. Health check backend
2. Scrape MLS Next schedules
3. Transform data to API format
4. Create/update games via API
5. Verify data integrity

See: [Match Scraper Guide](match-scraper.md)

---

## 🧪 Testing APIs

### Bruno Collections

Pre-built API test collections for Bruno.

```bash
# Install Bruno
brew install bruno

# Open collection
bruno open docs/08-integrations/bruno-testing.md
```

### cURL Examples

```bash
# Create game
curl -X POST http://localhost:8000/api/games \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "home_team_id": 1,
    "away_team_id": 2,
    "game_date": "2025-10-15",
    "season_id": 1,
    "age_group_id": 2,
    "game_type_id": 1
  }'

# Get standings
curl http://localhost:8000/api/standings?season_id=1&age_group_id=2
```

---

## 📖 Related Documentation

- **[API Development](../02-development/api-development.md)** - Creating endpoints
- **[Authentication](../03-architecture/authentication.md)** - Auth architecture
- **[Testing](../04-testing/)** - API testing strategies

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
