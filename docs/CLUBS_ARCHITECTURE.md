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

### GET /api/admin/clubs/logo-gaps (SB-1815)

Where crests are missing, without SQL. CLI: `mt club logo-gaps [--season ID] [--all]`.

**Authentication:** Admin only
**Query Parameters:**
- `season_id` (integer) - season to scope to (default: current)
- `all` (boolean) - report every team and club, ignoring the season

**Response:** `{season_id, teams_without_club: [{id, name, match_count}], clubs_without_logo: [{id, name}], clubs_external_logo: [{id, name, logo_url, host}]}`

- Scoped by default to teams with at least one match in the season and the clubs
  of those teams, excluding test clubs (`is_test`). `season_id` is `null` with `all=true`.
- A team with no club has no crest at all: the crest comes from the club.
- *External* means `logo_url` does not start with
  `{SUPABASE_URL}/storage/v1/object/public/club-logos/`, i.e. it is hot-linked
  from another site and breaks whenever that site changes. The prefix comes from
  `SUPABASE_URL`, so against a local database restored from prod every prod-hosted
  crest reads as external. Run it against prod for the real list.
- Fix a gap with `mt club set-logo <club> <file>` (uploads to the bucket) or
  `mt team set-club`.

### POST /api/admin/teams/{from_id}/merge-into/{into_id} (SB-1822)

Fold a duplicate team into the one to keep. CLI: `mt team merge FROM INTO [--yes]`
(id or exact full name, case-insensitive; no partial matching for a merge; always
shows the dry run first).

**Authentication:** Admin only
**Query Parameters:** `dry_run` (boolean, default `true`; `null` is also a dry run)

Calls the `merge_team(p_from, p_into, p_dry_run)` database function
(`20261128120000_merge_team_club.sql`, service role only). One transaction, with the
source row locked `FOR UPDATE` and the target `FOR KEY SHARE`:

- Every table referencing `teams.id` is repointed to `into_id`. A row that would
  collide with one the target already has (same mapping, same follow, same
  manager…) is dropped. A `player_team_history` collision keeps the target's row,
  which stays current if either copy was. A duplicate fixture (same date, teams and
  `unique_manual_match` key, and no differing external match id, tournament, round
  or side age group) is dropped. If the dropped copy has an external match id and the
  target has none, the id moves to the target (`tables["matches.match_id"]`).
- `power_ratings` / `power_rating_match_deltas` rows for the source are deleted.
  They are derived, and the next rating run recomputes them.
- The target's empty `club_id` and `city` are filled from the source (`copied`).
  When both teams have clubs and they differ, moved user profiles and invitations
  that carried the source's club take the target's.
- The source name is recorded as a `former_name` alias of the target
  (league-agnostic), so the feed resolves either spelling, unless a league-agnostic
  alias of that name already points at the target (`exists`). Then the source team
  is deleted.
- The response has `tables` (per-table `{moved, dropped}`), `alias`
  (`added` / `exists` / `same_name`), `copied`, `blockers`, and `complete`. A dry
  run that trips a constraint (usually the one a blocker names) stops early with
  `complete: false` and `error: {sqlstate, table, constraint}`; the backend logs it
  and the CLI prints it.

**Blockers**: a real run is refused (`409`) while any exist. When in doubt, the merge
blocks: merges are rare and a person can always resolve one by hand.
- a match between the two teams, which would become a team playing itself;
- `fixture_collision`: a target match on the same date and key that is a
  different fixture (another external match id, tournament, round or side age
  group);
- `duplicate_fixture_has_data`: a duplicate fixture whose source copy has user data
  (events, lineups, player stats, MOTW/MOTD, a bracket slot, notification threads),
  a score, penalty score
  or status that differs from the target's, a score lock, or a photo;
- `external_id_conflict`: a dropped copy's external match id has more than one place
  to go (several target rows, or several source copies for one target);
- two active players with the same jersey on the same team, season and age group;
- `channel_conflict`: both teams have the same notification channel (dropping one
  would take its members and delivery history with it);
- `alias_conflict`: a league-agnostic alias of the source's name points at a third
  team;
- `club_copy_conflict`: the target would take the source's club, which already has
  a team of the target's name in its league;
- `unlisted_reference`: after every known table moved, some table still references
  the source (a table added since the function was written). A real run raises
  naming it. Extend the function rather than lose those rows to a cascade.

Errors map by the function's own SQLSTATE, never by message text: `MTNF1` → `404`,
`MTBLK` → `409`, `MTSAM` (same or missing id) → `400`. Anything else is a logged
`500`.

### POST /api/admin/clubs/{from_id}/merge-into/{into_id} (SB-1822)

Fold a duplicate club into the one to keep. CLI: `mt club merge FROM INTO [--yes]`
(id or exact name).
Same shape as the team merge (`merge_club` function). Teams, user profiles,
invitations, chat messages (`match_events.chat_club_id`) and notification channels
move to the target. The target keeps its own crest, colours, city and website.
The source's values only fill the ones the target is missing. Stock colours
(`#6B7280` / `#374151`) count as missing. The response's `copied` lists which ones.
Blockers: a team with the same name and league in both clubs (merge the duplicate
teams first), the same notification channel or club channel platform in both clubs,
and any unlisted table still referencing the source.

```bash
mt team merge 581 937      # City SC San Diego -> City SC - San Diego
mt club merge 247 446
```

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
cd supabase
npx supabase db reset
./scripts/db_tools.sh restore

# Production (with backup!)
./switch-env.sh prod
./scripts/db_tools.sh backup prod
cd supabase
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
