# Match-Scraper Integration Plan

## Overview
Integration plan for connecting match-scraper with missing-table to handle MLS Next game data while preserving manual game entry capabilities for tournaments and scrimmages.

## Database Schema Changes

### Add to games table:
- `mls_match_id BIGINT NULL` - Optional MLS Next match identifier (e.g., 98667)
- `data_source VARCHAR(20) DEFAULT 'manual'` - Track origin ('manual', 'mls_scraper')
- `last_scraped_at TIMESTAMP NULL` - When scraper last updated this record
- `score_locked BOOLEAN DEFAULT FALSE` - Prevent scraper overwrites when manually locked

### Indexes:
- `CREATE INDEX idx_games_mls_match_id ON games(mls_match_id)` - Fast duplicate lookup
- `CREATE INDEX idx_games_data_source ON games(data_source)` - Filter by source

## Duplicate Prevention Logic

### For MLS Next games (with mls_match_id):
- Check `WHERE mls_match_id = 98667` before insert
- If exists, handle as update/conflict resolution

### For manual games (tournaments/scrimmages):
- Check `WHERE game_date = ? AND home_team_id = ? AND away_team_id = ? AND mls_match_id IS NULL`
- Prevents duplicate manual entries

## Conflict Resolution Strategy

### Score Priority Rules:
1. If `score_locked = TRUE` → Manual score wins, scraper skips
2. If `data_source = 'manual'` and scores differ → Alert admin, don't overwrite
3. If `data_source = 'mls_scraper'` → Scraper can update freely

### Workflow:
- Team admin scores match → Set `score_locked = TRUE` automatically
- Scraper finds same `mls_match_id` → Check lock status before updating
- Admin dashboard shows conflicts for review

## API Integration Approach

### Single Endpoint with Authentication:
- `POST /api/games` - Enhanced endpoint handles both manual and scraper data
- **Authentication required**: Service user account for match-scraper
- **Conflict resolution**: Built into the main endpoint via `data_source` field
- **Smart behavior**: Updates existing MLS games, prevents duplicates for manual games

### Service Account Setup:
```bash
# 1. Add to .env file (NEVER commit these values):
SCRAPER_USER_EMAIL=scraper-service@missing-table.local
SCRAPER_USER_PASSWORD=your-secure-password-here

# 2. Run the setup script:
cd backend && uv run python create_scraper_user.py
```

### Admin Tools:
- `PUT /api/admin/games/{id}/toggle-lock` - Lock/unlock scores manually
- `GET /api/admin/games/conflicts` - View games with score discrepancies
- `GET /api/admin/games/stats` - Data source statistics

## Enhanced Game Management

### Modified `add_game()` method:
- Auto-detect duplicates using appropriate strategy (MLS ID vs date/teams)
- Set `data_source` based on caller (API vs scraper)
- Return conflict info if duplicate found

### Team Admin Experience:
- Can score any game type (MLS, tournaments, scrimmages)
- Manual scores automatically protected from scraper overwrites
- Clear indicators showing data source in UI

## Scraper Integration Updates

### External match-scraper repository:
- Separate repository for match-scraper service
- Extract `match_id` from MLS site and include in API calls
- **Authenticate as service user** and use `POST /api/games` endpoint
- **Set `data_source: "mls_scraper"`** for all submissions
- Handle API responses for conflicts/updates/creation
- Batch process with proper error handling and retry logic
- Can run as independent service/cron job

### Service User Authentication:
- Email: `scraper-service@missing-table.local`
- Role: `admin` (for full API access)
- Use standard JWT authentication flow
- Script provided: `backend/create_scraper_user.py`

## Implementation Steps

1. **Database Migration**: Add new fields and indexes
2. **API Endpoints**: Create scraper-specific endpoints
3. **Conflict Detection**: Implement duplicate checking logic
4. **Scraper Updates**: Modify scraper to call API
5. **Admin Dashboard**: Add conflict management UI
6. **Testing**: End-to-end integration testing

## Benefits

- **Preserves Manual Control**: Team admins retain full control over tournament/scrimmage games
- **Prevents Duplicates**: Smart detection for both MLS and manual games
- **Conflict Resolution**: Clear workflow for handling score discrepancies
- **Data Integrity**: Source tracking and locking mechanisms
- **Scalable**: Handles mixed data sources efficiently