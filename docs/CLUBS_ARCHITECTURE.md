# Clubs Architecture Documentation

**Version:** 1.3.0
**Date:** 2025-11-01
**Migration:** `20251101000000_add_clubs_table.sql`
**Status:** ✅ Implemented, Ready for Deployment

---

## 📋 Table of Contents

- [Overview](#overview)
- [Why This Change](#why-this-change)
- [Architecture](#architecture)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Frontend Components](#frontend-components)
- [Migration Guide](#migration-guide)
- [Usage Examples](#usage-examples)
- [Testing](#testing)

---

## Overview

The **Clubs Architecture** introduces a proper separation between **clubs** (organizations) and **teams** (competition entities). This replaces the previous self-referencing `parent_club_id` approach with a cleaner, more scalable design.

### Key Concepts

- **Club**: An organization that fields teams in one or more leagues (e.g., "IFA")
- **Team**: A competition entity that belongs to a club AND a league (e.g., "IFA Academy")
- **League**: A competition category (e.g., "Homegrown", "Academy", "Elite")

### Example Structure

**Before (parent_club_id approach):**
```
teams table:
  - IFA (parent_club_id: NULL)          ← Parent club record
  - IFA Academy (parent_club_id: IFA)   ← Child team
  - IFA Homegrown (parent_club_id: IFA) ← Child team
```

**After (clubs architecture):**
```
clubs table:
  - IFA (city: Weymouth, MA)

teams table:
  - IFA Academy (club_id: IFA, league_id: Academy)
  - IFA Homegrown (club_id: IFA, league_id: Homegrown)
  - IFA Select (club_id: IFA, league_id: Elite)
```

---

## Why This Change

### Problems with parent_club_id

1. **Conflated Concepts**: Used teams table to represent both clubs and teams
2. **Data Duplication**: Parent club records mixed with team records
3. **Complex Queries**: Self-referencing joins were confusing
4. **Limited Metadata**: Couldn't store club-specific data (website, description)
5. **Workarounds Needed**: Required team_aliases to display names correctly

### Benefits of Clubs Architecture

✅ **Clean Separation**: Clubs and teams are distinct entities
✅ **Better Data Model**: Each table has a single, clear purpose
✅ **Rich Metadata**: Clubs can have website, description, etc.
✅ **Simpler Queries**: Direct foreign key relationships
✅ **No Workarounds**: No need for team_aliases
✅ **Scalable**: Easy to add more club or league data

---

## Architecture

### Entity Relationships

```
┌──────────────┐
│    clubs     │
│  (orgs)      │
└──────┬───────┘
       │ 1
       │
       │ N
┌──────┴───────┐       ┌──────────────┐
│    teams     │──────►│   leagues    │
│ (competition)│  N:1  │ (categories) │
└──────┬───────┘       └──────────────┘
       │
       │ 1
       │
       │ N
┌──────┴───────┐
│   matches    │
│ (results)    │
└──────────────┘
```

### Data Flow

```
1. Admin creates Club (IFA)
   ↓
2. Admin creates Teams linked to Club + League
   - IFA Academy (club: IFA, league: Academy)
   - IFA Homegrown (club: IFA, league: Homegrown)
   ↓
3. Matches use team IDs
   ↓
4. UI displays:
   - "IFA Academy" (no alias needed)
   - Teams grouped by club (via club_id)
```

---

## Database Schema

### Clubs Table

```sql
CREATE TABLE clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    city VARCHAR(100),
    website VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Columns:**
- `id` - Primary key
- `name` - Club name (unique, e.g., "IFA")
- `city` - Location (e.g., "Weymouth, MA")
- `website` - Club website URL
- `description` - About the club
- `is_active` - Soft delete flag
- `created_at` / `updated_at` - Timestamps

### Teams Table Updates

```sql
ALTER TABLE teams
ADD COLUMN club_id INTEGER REFERENCES clubs(id) ON DELETE RESTRICT,
ADD COLUMN league_id INTEGER REFERENCES leagues(id) ON DELETE RESTRICT;
```

**New Columns:**
- `club_id` - Foreign key to clubs (nullable for independent teams)
- `league_id` - Foreign key to leagues (required)

**Dropped Columns:**
- `parent_club_id` - No longer needed

### Views

```sql
CREATE VIEW teams_with_details AS
SELECT
    t.id,
    t.name AS team_name,
    t.city,
    c.name AS club_name,
    l.name AS league_name,
    t.created_at,
    t.updated_at
FROM teams t
LEFT JOIN clubs c ON t.club_id = c.id
JOIN leagues l ON t.league_id = l.id;
```

### Helper Functions

```sql
-- Get all teams for a club
get_club_teams(p_club_id INTEGER) RETURNS TABLE(...)

-- Get teams for club in specific league
get_club_league_teams(p_club_id INTEGER, p_league_id INTEGER) RETURNS TABLE(...)
```

---

## API Endpoints

### GET /api/clubs

List all clubs with optional team information.

**Authentication:** Required
**Query Parameters:**
- `include_teams` (boolean, default: true) - Include team counts

**Response:**
```json
[
  {
    "id": 1,
    "name": "IFA",
    "city": "Weymouth, MA",
    "website": "https://ifa.com",
    "description": "Premier youth soccer club",
    "team_count": 3,
    "teams": [
      {"id": 2, "name": "IFA Academy", "league_name": "Academy"},
      {"id": 3, "name": "IFA Homegrown", "league_name": "Homegrown"}
    ]
  }
]
```

### POST /api/clubs

Create a new club.

**Authentication:** Admin only
**Request Body:**
```json
{
  "name": "IFA",
  "city": "Weymouth, MA",
  "website": "https://ifa.com",
  "description": "Premier youth soccer club"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "IFA",
  "city": "Weymouth, MA",
  "website": "https://ifa.com",
  "description": "Premier youth soccer club",
  "created_at": "2025-11-01T12:00:00Z"
}
```

### DELETE /api/clubs/{club_id}

Delete a club (only if no teams are linked).

**Authentication:** Admin only
**Parameters:** `club_id` (path, integer)
**Response:** `204 No Content` on success

### GET /api/teams (Enhanced)

Teams endpoint now supports club filtering.

**Query Parameters:**
- `club_id` (integer) - Filter teams by club
- `league_id` (integer) - Filter teams by league

**Example:**
```bash
GET /api/teams?club_id=1&league_id=2
```

---

## Frontend Components

### AdminClubs.vue

**Location:** `frontend/src/components/admin/AdminClubs.vue`

**Features:**
- List all clubs with team counts
- Create new club with website/description
- Delete club (if no teams)
- View teams for each club

**UI:**
```
┌───────────────────────────────────────┐
│ Clubs                                 │
│                                       │
│ [Create New Club]                     │
│                                       │
│ ┌─────────────────────────────────┐  │
│ │ IFA                             │  │
│ │ Weymouth, MA                    │  │
│ │ 3 teams                         │  │
│ │ https://ifa.com                 │  │
│ │ [Delete]                        │  │
│ └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

### LeagueTable.vue (Updated)

**Removed:**
- Team aliases logic
- `fetchTeamAliases()` function
- `getTeamDisplayName()` complexity

**Now:**
- Teams display their actual name (no aliases needed)
- Filtered by league via `league_id`

### MatchesView.vue (Updated)

Same changes as LeagueTable.vue - simplified team name display.

---

## Migration Guide

### Automated Migration

The migration `20251101000000_add_clubs_table.sql` handles all data transformation automatically:

**Steps Performed:**
1. Creates `clubs` table
2. Finds all parent club teams (teams referenced by `parent_club_id`)
3. Creates club records for these parent teams
4. Updates child teams to reference new clubs via `club_id`
5. **Deletes old parent club team records** (they're now in clubs table)
6. Sets all teams to "Homegrown" league by default
7. Drops `parent_club_id` column and related functions
8. Creates new helper functions and views

### Running Migration

```bash
# Local environment
cd supabase-local
npx supabase db reset
./scripts/db_tools.sh restore

# Production (with backup!)
./switch-env.sh prod
./scripts/db_tools.sh backup prod
cd supabase-local
npx supabase db push --linked
```

### After Migration

1. **Review clubs table:**
   ```sql
   SELECT * FROM clubs ORDER BY name;
   ```

2. **Review teams structure:**
   ```sql
   SELECT * FROM teams_with_details ORDER BY club_name, league_name, team_name;
   ```

3. **Update team league assignments:**
   ```sql
   UPDATE teams SET league_id = X WHERE name = 'Team Name';
   ```

4. **Verify old parent club records are gone:**
   ```sql
   -- Should return 0 rows
   SELECT * FROM teams WHERE id IN (
     SELECT DISTINCT parent_club_id FROM teams WHERE parent_club_id IS NOT NULL
   );
   ```

---

## Usage Examples

### Create a Club

```bash
# Admin creates IFA club
curl -X POST https://dev.missingtable.com/api/clubs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "IFA",
    "city": "Weymouth, MA",
    "website": "https://ifa.com",
    "description": "Premier youth soccer club"
  }'
```

### Create Teams for Club

```sql
-- Get club ID and league IDs
SELECT id FROM clubs WHERE name = 'IFA';
SELECT id, name FROM leagues;

-- Create teams
INSERT INTO teams (name, city, club_id, league_id)
VALUES
  ('IFA Academy', 'Weymouth, MA', 1, 1),
  ('IFA Homegrown', 'Weymouth, MA', 1, 2);
```

### Query Club Teams

```bash
# Get all teams for IFA
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/clubs/1/teams

# Filter teams by club
curl -H "Authorization: Bearer $TOKEN" \
  'https://dev.missingtable.com/api/teams?club_id=1'
```

### Display Team Names

Frontend:
```javascript
// No more aliases - just use team.name directly
const getTeamDisplayName = (team) => team.name;
```

---

## Testing

### Verify Migration

```bash
# Check schema version
psql $DATABASE_URL -c "SELECT * FROM get_schema_version();"
# Should show: v1.3.0

# Count clubs
psql $DATABASE_URL -c "SELECT COUNT(*) FROM clubs;"

# Verify no parent club teams remain
psql $DATABASE_URL -c "
  SELECT COUNT(*) FROM teams
  WHERE id IN (
    SELECT DISTINCT parent_club_id FROM teams WHERE parent_club_id IS NOT NULL
  );
"
# Should return: 0
```

### Test API Endpoints

```bash
# Test clubs endpoint
curl -H "Authorization: Bearer $TOKEN" \
  https://dev.missingtable.com/api/clubs

# Test create club
curl -X POST https://dev.missingtable.com/api/clubs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Club","city":"Boston, MA"}'

# Test delete club
curl -X DELETE https://dev.missingtable.com/api/clubs/999 \
  -H "Authorization: Bearer $TOKEN"
```

### Frontend Testing

1. Navigate to Admin Panel → Clubs tab
2. Verify "Clubs" tab is visible
3. Create a new club
4. Verify team count displays
5. Delete a club (only works if no teams)
6. Check LeagueTable shows team names correctly (no aliases)

---

## Related Documentation

- **[Database Schema](./database-schema.md)** - Full schema reference
- **[Architecture Overview](./03-architecture/README.md)** - System architecture
- **[Migration Best Practices](./MIGRATION_BEST_PRACTICES.md)** - Migration guidelines
- **[API Documentation](./API_REFERENCE.md)** - Complete API reference

---

## Rollback Plan

If issues arise, rollback is possible but **NOT recommended** as data has been transformed:

```bash
# Restore from backup (recommended)
./scripts/db_tools.sh restore backup_file.json

# OR manually recreate parent_club_id structure (complex, not recommended)
```

**Best Practice:** Test thoroughly in DEV before applying to PROD, and always backup before migrations.

---

## Success Criteria

✅ **Database:**
- [x] Clubs table exists with proper schema
- [x] Teams have club_id and league_id columns
- [x] Old parent_club_id column removed
- [x] Old parent club team records deleted
- [x] Helper functions work correctly

✅ **Backend:**
- [x] Club CRUD endpoints functional
- [x] Team endpoints support club filtering
- [x] DAO layer updated
- [x] No team_aliases code remains

✅ **Frontend:**
- [x] AdminClubs.vue component works
- [x] Clubs tab visible in admin panel
- [x] Team name display simplified (no aliases)
- [x] Frontend linter passes

✅ **Deployment:**
- [ ] Migration applied to DEV
- [ ] Migration applied to PROD
- [ ] All endpoints tested in production

---

**Last Updated:** 2025-11-01
**Schema Version:** 1.3.0
**Migration File:** `supabase/migrations/20251101000000_add_clubs_table.sql`
