# Club Multi-League Analysis: Academy vs Homegrown

**Date:** 2025-10-30
**Schema Version:** 1.1.0
**Question:** Do we need to create separate team records for clubs that play in both Academy and Homegrown leagues?

## Current Schema Structure

### Teams Table (Current)
```sql
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(100),
    academy_team BOOLEAN DEFAULT false,  -- ⚠️ Existing field
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Team Mappings (Current)
```sql
CREATE TABLE team_mappings (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    age_group_id INTEGER NOT NULL REFERENCES age_groups(id) ON DELETE CASCADE,
    division_id INTEGER REFERENCES divisions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, age_group_id, division_id)
);
```

### Current Hierarchy
```
League (Homegrown or Academy)
  └── Division (Champions, Premier I, etc.)
      └── Team Mapping (links team to age group + division)
          └── Team (IFA, New England Revolution, etc.)
```

## The Problem

Some clubs (like IFA, New England Revolution, NYCFC) may have teams in **both** leagues:
- **Homegrown League** - Local recreational/competitive teams
- **Academy League** - MLS Next or professional academy teams

**Example:**
- IFA U14 Homegrown (plays in Homegrown League, Champions division)
- IFA U14 Academy (plays in Academy League, Premier I division)

These are **different teams** with:
- Different rosters
- Different coaches
- Different schedules
- Different standings

## Three Possible Approaches

### Option 1: Single Team Record + League Context (CURRENT APPROACH)

**Structure:**
- One `teams` record for "IFA"
- Multiple `team_mappings` entries linking IFA to different divisions/leagues
- The `academy_team` boolean field already exists

**Pros:**
- ✅ Single source of truth for club information (name, city, etc.)
- ✅ Easy to query "all teams for a club"
- ✅ Minimal duplication
- ✅ Already has `academy_team` field

**Cons:**
- ❌ Confusing when IFA plays in multiple leagues
- ❌ The `academy_team` boolean doesn't work if club has both
- ❌ Team-level metadata (coach, roster) would conflict
- ❌ Can't easily distinguish "IFA Academy U14" from "IFA Homegrown U14"

**Current Data Example:**
```sql
-- Single team record
teams: { id: 19, name: "IFA", city: "Weymouth, MA", academy_team: false }

-- Multiple mappings
team_mappings:
  - { team_id: 19, age_group_id: 2, division_id: 1 }  -- U14 in Champions (Homegrown)
  - { team_id: 19, age_group_id: 2, division_id: 5 }  -- U14 in Premier I (Academy)
```

---

### Option 2: Separate Team Records per League (RECOMMENDED)

**Structure:**
- Create distinct team records: "IFA Homegrown" and "IFA Academy"
- Each team maps to appropriate divisions within their league
- Add `parent_club_id` to link related teams

**Schema Changes Needed:**
```sql
-- Add parent club tracking
ALTER TABLE teams
ADD COLUMN parent_club_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;

-- Add index
CREATE INDEX idx_teams_parent_club ON teams(parent_club_id);
```

**Data Example:**
```sql
-- Club level (optional parent)
teams: { id: 100, name: "IFA", city: "Weymouth, MA", parent_club_id: NULL }

-- League-specific teams
teams: { id: 101, name: "IFA Homegrown", city: "Weymouth, MA", parent_club_id: 100 }
teams: { id: 102, name: "IFA Academy", city: "Weymouth, MA", parent_club_id: 100 }

-- Mappings
team_mappings:
  - { team_id: 101, age_group_id: 2, division_id: 1 }  -- IFA Homegrown U14 in Champions
  - { team_id: 102, age_group_id: 2, division_id: 5 }  -- IFA Academy U14 in Premier I
```

**Pros:**
- ✅ Clear separation of academy vs homegrown teams
- ✅ Can have different coaches, rosters, metadata per team
- ✅ Standings are clearly separated
- ✅ Team names are explicit (no ambiguity)
- ✅ Easy to query "all academy teams" or "all homegrown teams"
- ✅ Future-proof for additional team-level metadata

**Cons:**
- ❌ More team records (2x for clubs in both leagues)
- ❌ Need to maintain parent_club_id relationships
- ❌ Potential confusion if team names aren't clear

---

### Option 3: Team Groups/Clubs Table (MOST COMPLEX)

**Structure:**
- New `clubs` table for organizations (IFA, NYCFC, etc.)
- `teams` table references clubs
- Teams are league-specific

**Schema Changes Needed:**
```sql
CREATE TABLE clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    city VARCHAR(100),
    is_academy BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE teams
ADD COLUMN club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
ADD COLUMN league_context VARCHAR(50);  -- 'academy', 'homegrown', etc.

-- Drop academy_team since it's now at club level
ALTER TABLE teams DROP COLUMN academy_team;
```

**Pros:**
- ✅ Clean separation of club vs team concepts
- ✅ Most flexible for future expansion
- ✅ Clear data model

**Cons:**
- ❌ Major schema change
- ❌ Requires data migration
- ❌ More complex queries
- ❌ Might be over-engineering

---

## Analysis & Recommendation

### Current State Assessment

Looking at your current data:
- 29 teams total
- Teams like "New England Revolution", "New York City FC", "Philadelphia Union" are MLS clubs
- Teams like "IFA", "Bayside FC", "NEFC" could have both academy and homegrown programs
- The `academy_team` boolean exists but is limited

### Real-World Scenario

**IFA Example:**
- IFA runs a Homegrown program (local competitive teams)
- IFA might also run an Academy program (higher level)
- The U14 Homegrown team and U14 Academy team are **different entities**:
  - Different rosters (20+ different players)
  - Different coaches
  - Different schedules
  - Different standings
  - Play in different leagues

**This is NOT like:**
- Same team playing in multiple tournaments
- Same roster in different competitions

**This IS like:**
- Varsity vs JV teams (different players, different rosters)
- A-team vs B-team

### Recommended Approach: **Option 2** (Separate Team Records)

**Reasoning:**
1. **Matches real-world structure** - These are genuinely different teams
2. **Simple to implement** - Minor schema change (add `parent_club_id`)
3. **Clear semantics** - "IFA Academy" vs "IFA Homegrown" is explicit
4. **Backwards compatible** - Can migrate existing data gradually
5. **Scalable** - Works if clubs expand to multiple leagues
6. **Team-level metadata** - Each team can have its own coach, roster, etc.

**Implementation Plan:**
1. Add `parent_club_id` column to teams table
2. Keep existing `academy_team` boolean for backward compatibility
3. Create naming convention: "{Club Name} {League Context}"
   - "IFA Academy"
   - "IFA Homegrown"
   - "New England Revolution Academy"
4. Migrate existing teams:
   - If `academy_team = true`, suffix with "Academy"
   - If `academy_team = false`, suffix with "Homegrown" (or leave as-is)
5. Create parent club records (optional) for clubs with multiple teams

### Migration Strategy

**Phase 1: Add Column (Non-breaking)**
```sql
ALTER TABLE teams
ADD COLUMN parent_club_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;

CREATE INDEX idx_teams_parent_club ON teams(parent_club_id);
```

**Phase 2: Create Parent Clubs (Optional)**
```sql
-- For clubs with teams in multiple leagues
INSERT INTO teams (name, city) VALUES ('IFA', 'Weymouth, MA');
-- Returns id: 100

-- Update child teams
UPDATE teams SET parent_club_id = 100 WHERE name LIKE 'IFA%';
```

**Phase 3: Rename Teams for Clarity**
```sql
-- Make team names explicit
UPDATE teams SET name = 'IFA Academy' WHERE id = 19 AND academy_team = true;
UPDATE teams SET name = 'IFA Homegrown' WHERE id = 19 AND academy_team = false;
```

### Query Examples

**Get all teams for a club:**
```sql
SELECT * FROM teams WHERE parent_club_id = 100 OR id = 100;
```

**Get all academy teams:**
```sql
SELECT t.* FROM teams t
JOIN team_mappings tm ON t.id = tm.team_id
JOIN divisions d ON tm.division_id = d.id
JOIN leagues l ON d.league_id = l.id
WHERE l.name = 'Academy';
```

**Get standings for a specific team:**
```sql
-- Clear which team: "IFA Academy" vs "IFA Homegrown"
SELECT * FROM matches WHERE home_team_id = 101;  -- IFA Academy
SELECT * FROM matches WHERE home_team_id = 102;  -- IFA Homegrown
```

---

## Alternative: Hybrid Approach

If you want to avoid duplication but maintain clarity:

**Keep single team records but add context to team_mappings:**

```sql
ALTER TABLE team_mappings
ADD COLUMN team_context VARCHAR(100);  -- "Academy U14", "Homegrown U14"

-- Now you can have:
team_mappings:
  - { team_id: 19, age_group_id: 2, division_id: 1, team_context: "Homegrown" }
  - { team_id: 19, age_group_id: 2, division_id: 5, team_context: "Academy" }
```

**Pros:**
- ✅ Minimal schema change
- ✅ Maintains single team record

**Cons:**
- ❌ Context is buried in mappings table
- ❌ Team-level metadata still conflicts
- ❌ Less intuitive querying

---

## Final Recommendation

**Go with Option 2: Separate Team Records per League**

**Benefits:**
1. Clearest semantics
2. Most flexible for future team metadata (rosters, coaches)
3. Simplest to understand for users
4. Easy to implement
5. Matches real-world structure

**Implementation:**
1. Add `parent_club_id` column (migration)
2. Establish naming convention
3. Create separate team records for clubs in multiple leagues
4. Link via `parent_club_id` for club-level queries

**Next Steps:**
1. Write migration to add `parent_club_id`
2. Update schema documentation
3. Update frontend to display club relationships
4. Update match-scraper integration guide

---

## Questions to Consider

1. **Will teams ever move between leagues?**
   - If yes → Separate records are cleaner
   - If no → Either approach works

2. **Do you need team-level metadata (coach, roster)?**
   - If yes → Separate records required
   - If no → Single record might work

3. **How important is query simplicity?**
   - Simple queries → Separate records
   - Don't mind complex JOINs → Single record

4. **How many clubs will have teams in both leagues?**
   - Many → Separate records justified
   - Few → Single record acceptable

Based on typical soccer organization structure, **separate team records** is the industry-standard approach.

---

**Last Updated:** 2025-10-30
**Schema Version:** 1.1.0
**Status:** Analysis complete, awaiting decision
