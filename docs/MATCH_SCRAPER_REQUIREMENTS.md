# Match-Scraper Requirements

## Division ID Requirement

### Overview
Starting 2025-10-26, **all League matches MUST include a `division_id`** when submitting to the Missing Table API. Friendly and Tournament matches can have `division_id` set to `null`.

### API Validation

The following endpoints now validate `division_id` for League matches:

- `POST /api/matches` - Create match
- `POST /api/match-scraper/matches` - Create/update scraped match
- `PUT /api/matches/{match_id}` - Update match
- `PATCH /api/matches/{match_id}` - Partial update match

### Error Response

If you submit a League match without `division_id`, you'll receive:

```json
{
  "detail": "division_id is required for League matches"
}
```

**HTTP Status:** 422 Unprocessable Entity

### Match Type Requirements

| Match Type | division_id Required? |
|------------|----------------------|
| League     | ✅ YES               |
| Friendly   | ❌ NO (can be null)  |
| Tournament | ❌ NO (can be null)  |
| Playoff    | ❌ NO (can be null)  |

### How to Get Division ID

#### Option 1: Query Division by Name
```python
# Get Northeast division
response = requests.get(
    f"{base_url}/api/divisions",
    headers={"Authorization": f"Bearer {token}"}
)
divisions = response.json()
northeast = next(d for d in divisions if d['name'] == 'Northeast')
division_id = northeast['id']  # Use this in your match data
```

#### Option 2: Lookup from Team
```python
# Get division from team's age group mapping
response = requests.get(
    f"{base_url}/api/teams/{team_id}",
    headers={"Authorization": f"Bearer {token}"}
)
team = response.json()
# Teams have division_id in their team_mappings for each age_group
```

### Example Match Submission

#### ✅ Valid - League match with division_id
```python
match_data = {
    "match_date": "2025-11-01",
    "home_team_id": 22,
    "away_team_id": 19,
    "home_score": 2,
    "away_score": 1,
    "season_id": 3,
    "age_group_id": 2,
    "match_type_id": 1,  # League
    "division_id": 1,    # ✅ REQUIRED for League
    "status": "completed",
    "source": "match-scraper",
    "external_match_id": "99999"
}
```

#### ❌ Invalid - League match without division_id
```python
match_data = {
    "match_date": "2025-11-01",
    "home_team_id": 22,
    "away_team_id": 19,
    "home_score": 2,
    "away_score": 1,
    "season_id": 3,
    "age_group_id": 2,
    "match_type_id": 1,  # League
    "division_id": None,  # ❌ WILL FAIL
    "status": "completed"
}
```

#### ✅ Valid - Friendly match without division_id
```python
match_data = {
    "match_date": "2025-11-01",
    "home_team_id": 22,
    "away_team_id": 19,
    "home_score": 2,
    "away_score": 1,
    "season_id": 3,
    "age_group_id": 2,
    "match_type_id": 3,  # Friendly
    "division_id": None,  # ✅ OK for Friendly
    "status": "completed"
}
```

### Database Migration

A database trigger has been created to enforce this at the database level:

**Migration:** `supabase/migrations/20251026000022_add_league_division_constraint.sql`

To apply this migration to your environment:

```bash
# Option 1: Via Supabase CLI (if authenticated)
npx supabase db push

# Option 2: Manually via Supabase SQL Editor
# Copy contents of migration file and execute in SQL Editor:
# https://supabase.com/dashboard/project/YOUR_PROJECT/sql
```

### Impact

- **23 League matches** were backfilled with `division_id=1` (Northeast) on 2025-10-26
- **All new League matches** must include `division_id`
- **Friendly/Tournament matches** can omit `division_id`

### Related Files

- API validation: `backend/app.py` (lines 1156-1162, 1856-1862, 1203-1209, 1312-1320)
- DAO method: `backend/dao/enhanced_data_access_fixed.py` (lines 155-162)
- Database migration: `supabase/migrations/20251026000022_add_league_division_constraint.sql`
- Backfill script: `backend/backfill_league_divisions.py`

### Questions?

Contact the Missing Table team or check the API documentation at:
- Dev: https://dev.missingtable.com/api/docs
- Prod: https://missingtable.com/api/docs

---

**Last Updated:** 2025-10-26
**Version:** 1.0
