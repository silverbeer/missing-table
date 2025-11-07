# Parent Club Migration Guide

**Migration:** 20251030184100_add_parent_club_to_teams
**Schema Version:** 1.2.0
**Date:** 2025-10-30
**Status:** ✅ Tested and Verified

## Overview

This migration adds support for parent club hierarchies, enabling clubs to have multiple teams across different leagues (e.g., "IFA Academy" and "IFA Homegrown").

## What Changed

### Schema Changes

**Added to `teams` table:**
- `parent_club_id` - INTEGER, self-referencing foreign key to teams(id)
- Indexes on `parent_club_id`
- Constraint to prevent self-reference
- Trigger to enforce single-level hierarchy

### New Functions

1. **`get_club_teams(p_club_id INTEGER)`**
   - Returns all teams for a club (parent + children)
   - Useful for querying "all IFA teams"

2. **`is_parent_club(p_team_id INTEGER)`**
   - Returns true if team has child teams
   - Useful for UI conditional logic

3. **`get_parent_club(p_team_id INTEGER)`**
   - Returns parent club information for a team
   - Useful for breadcrumb navigation

### New Views

**`teams_with_parent`**
- Convenient view joining teams with their parent club info
- Includes `is_standalone` and `is_parent_club` boolean flags

## Migration Verification

Migration has been tested and verified on local environment:

```
✅ get_club_teams() function works
✅ is_parent_club() function works
✅ get_parent_club() function works
✅ teams_with_parent view exists
✅ Schema version: 1.2.0
✅ teams table has parent_club_id column
```

## Data Model

### Before Migration

```
teams
├── id: 19
├── name: "IFA"
├── city: "Weymouth, MA"
└── academy_team: false

team_mappings (showing same team in multiple leagues - CONFUSING)
├── team_id: 19, division_id: 1  (Homegrown league)
└── team_id: 19, division_id: 5  (Academy league)
```

### After Migration (Recommended Structure)

```
teams
├── id: 100 (Parent Club)
│   ├── name: "IFA"
│   ├── city: "Weymouth, MA"
│   └── parent_club_id: NULL
│
├── id: 101 (Child Team - Academy)
│   ├── name: "IFA Academy"
│   ├── city: "Weymouth, MA"
│   ├── academy_team: true
│   └── parent_club_id: 100
│
└── id: 102 (Child Team - Homegrown)
    ├── name: "IFA Homegrown"
    ├── city: "Weymouth, MA"
    ├── academy_team: false
    └── parent_club_id: 100

team_mappings (each team has clear, separate mappings)
├── team_id: 101, division_id: 5  (IFA Academy in Academy league)
└── team_id: 102, division_id: 1  (IFA Homegrown in Homegrown league)
```

## Migration Steps for Existing Data

**IMPORTANT:** This migration adds the column but does NOT automatically reorganize existing data. You must manually migrate data for clubs with multiple teams.

### Step 1: Identify Clubs with Multiple Teams

```sql
-- Find teams that appear in multiple leagues
SELECT DISTINCT t.id, t.name, COUNT(DISTINCT d.league_id) as league_count
FROM teams t
JOIN team_mappings tm ON t.id = tm.team_id
JOIN divisions d ON tm.division_id = d.id
GROUP BY t.id, t.name
HAVING COUNT(DISTINCT d.league_id) > 1;
```

### Step 2: Create Parent Club Records

For each club with multiple league teams:

```sql
-- Example: Create parent club for IFA
INSERT INTO teams (name, city)
VALUES ('IFA', 'Weymouth, MA')
RETURNING id;
-- Returns: 100 (use this as parent_club_id)
```

### Step 3: Create Separate Team Records

```sql
-- Create Academy team
INSERT INTO teams (name, city, academy_team, parent_club_id)
VALUES ('IFA Academy', 'Weymouth, MA', true, 100)
RETURNING id;
-- Returns: 101

-- Create Homegrown team
INSERT INTO teams (name, city, academy_team, parent_club_id)
VALUES ('IFA Homegrown', 'Weymouth, MA', false, 100)
RETURNING id;
-- Returns: 102
```

### Step 4: Update Team Mappings

```sql
-- Move Academy league mappings to new Academy team
UPDATE team_mappings
SET team_id = 101  -- IFA Academy
WHERE team_id = 19  -- Old IFA
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Academy')
  );

-- Move Homegrown league mappings to new Homegrown team
UPDATE team_mappings
SET team_id = 102  -- IFA Homegrown
WHERE team_id = 19  -- Old IFA
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Homegrown')
  );
```

### Step 5: Update Matches

```sql
-- Update matches for Academy team
UPDATE matches
SET home_team_id = 101
WHERE home_team_id = 19
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Academy')
  );

UPDATE matches
SET away_team_id = 101
WHERE away_team_id = 19
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Academy')
  );

-- Update matches for Homegrown team
UPDATE matches
SET home_team_id = 102
WHERE home_team_id = 19
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Homegrown')
  );

UPDATE matches
SET away_team_id = 102
WHERE away_team_id = 19
  AND division_id IN (
      SELECT id FROM divisions
      WHERE league_id = (SELECT id FROM leagues WHERE name = 'Homegrown')
  );
```

### Step 6: Clean Up Old Team Record (Optional)

```sql
-- Delete old ambiguous team record
-- ONLY do this after verifying all mappings and matches are updated
DELETE FROM teams WHERE id = 19;
```

## Naming Conventions

**Recommended naming format:**
- Parent Club: `"{Club Name}"` (e.g., "IFA", "New England Revolution")
- Child Teams: `"{Club Name} {League Context}"` (e.g., "IFA Academy", "IFA Homegrown", "IFA Development")

**Alternative formats:**
- `"{Club Name} - {League}"` (e.g., "IFA - Academy")
- `"{Club Name} ({League})"` (e.g., "IFA (Academy)")

Choose one format and be consistent across your database.

## Query Examples

### Get All Teams for a Club

```sql
-- Using function
SELECT * FROM get_club_teams(100);

-- Using view
SELECT * FROM teams_with_parent
WHERE parent_club_id = 100 OR id = 100
ORDER BY is_parent_club DESC, name;
```

### Get All Parent Clubs

```sql
-- Clubs that have child teams
SELECT t.* FROM teams t
WHERE parent_club_id IS NULL
  AND EXISTS (SELECT 1 FROM teams WHERE parent_club_id = t.id);

-- Using function
SELECT t.* FROM teams t
WHERE is_parent_club(t.id) = true;
```

### Get All Standalone Teams

```sql
-- Teams with no parent and no children
SELECT * FROM teams
WHERE parent_club_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM teams c WHERE c.parent_club_id = teams.id);
```

### Get All Child Teams

```sql
SELECT * FROM teams
WHERE parent_club_id IS NOT NULL;
```

### Get Parent for a Team

```sql
-- Using function
SELECT * FROM get_parent_club(101);

-- Using view
SELECT parent_club_name, parent_club_city
FROM teams_with_parent
WHERE id = 101;
```

## Constraints & Validation

### Single-Level Hierarchy

The migration enforces a **single-level parent-child hierarchy**:

✅ Allowed:
```
IFA (parent_club_id: NULL)
  └── IFA Academy (parent_club_id: points to IFA)
```

❌ NOT Allowed:
```
IFA (parent_club_id: NULL)
  └── IFA Academy (parent_club_id: points to IFA)
      └── IFA Academy U14 (parent_club_id: points to IFA Academy)  ❌ BLOCKED
```

### Prevented Scenarios

1. **Self-reference:**
   ```sql
   UPDATE teams SET parent_club_id = id WHERE id = 100;
   -- ❌ ERROR: Constraint violation
   ```

2. **Circular reference:**
   ```sql
   -- Team A → parent_club_id: B
   -- Team B → parent_club_id: A
   -- ❌ ERROR: Blocked by trigger
   ```

3. **Multi-level hierarchy:**
   ```sql
   -- Team A (parent) → Team B (child) → Team C (grandchild)
   -- ❌ ERROR: Team B cannot be both child and parent
   ```

## Frontend Integration

### Display Team with Parent

```javascript
// Using teams_with_parent view
const { data } = await supabase
  .from('teams_with_parent')
  .select('*')
  .eq('id', teamId)
  .single();

if (data.parent_club_name) {
  console.log(`${data.parent_club_name} > ${data.name}`);
  // Output: "IFA > IFA Academy"
} else if (data.is_parent_club) {
  console.log(`${data.name} (Parent Club)`);
  // Output: "IFA (Parent Club)"
} else {
  console.log(data.name);
  // Output: "Standalone Team"
}
```

### Get All Teams for a Club (Dropdown)

```javascript
const { data } = await supabase
  .rpc('get_club_teams', { p_club_id: clubId });

// Returns:
// [
//   { id: 100, name: "IFA", is_parent: true },
//   { id: 101, name: "IFA Academy", is_parent: false },
//   { id: 102, name: "IFA Homegrown", is_parent: false }
// ]
```

## Rollback

If you need to rollback this migration:

```sql
-- 1. Remove trigger
DROP TRIGGER IF EXISTS validate_parent_club_hierarchy ON teams;
DROP FUNCTION IF EXISTS check_parent_club_hierarchy();

-- 2. Remove view
DROP VIEW IF EXISTS teams_with_parent;

-- 3. Remove functions
DROP FUNCTION IF EXISTS get_club_teams(INTEGER);
DROP FUNCTION IF EXISTS is_parent_club(INTEGER);
DROP FUNCTION IF EXISTS get_parent_club(INTEGER);

-- 4. Remove indexes
DROP INDEX IF EXISTS idx_teams_parent_club_id;
DROP INDEX IF EXISTS idx_teams_parent_club_age_group;

-- 5. Remove constraint
ALTER TABLE teams DROP CONSTRAINT IF EXISTS teams_parent_not_self;

-- 6. Remove column
ALTER TABLE teams DROP COLUMN IF EXISTS parent_club_id;

-- 7. Revert schema version
DELETE FROM schema_version WHERE version = '1.2.0';
```

## Next Steps

1. **Identify clubs with multi-league presence**
   - Run analysis query from Step 1 above
   - Document which clubs need migration

2. **Create parent club records**
   - For each multi-league club, create parent record
   - Document parent_club_id mappings

3. **Create separate team records**
   - Create Academy team records
   - Create Homegrown team records
   - Update parent_club_id references

4. **Migrate team_mappings**
   - Update mappings to point to correct team records
   - Verify no orphaned mappings

5. **Migrate matches**
   - Update home_team_id and away_team_id
   - Verify match integrity

6. **Update frontend**
   - Use `teams_with_parent` view for display
   - Show parent club hierarchy in UI
   - Add filtering by parent club

7. **Deploy to environments**
   - Apply to local ✅ (Complete)
   - Apply to dev
   - Test thoroughly in dev
   - Apply to production

## Support

For questions about this migration:
- See analysis: `docs/CLUB_LEAGUE_ANALYSIS.md`
- See diagrams: `docs/club-league-options-diagram.md`
- See schema docs: `docs/database-schema.md`

---

**Migration Author:** Claude Code
**Last Updated:** 2025-10-30
**Schema Version:** 1.2.0
**Status:** ✅ Ready for deployment
