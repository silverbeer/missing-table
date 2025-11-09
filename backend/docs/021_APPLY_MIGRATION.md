# Migration 021: Add Updated_At Trigger

## Problem Statement
Match scores were being updated correctly by the match-scraper, but the `updated_at` timestamp was not being updated. This made it difficult to track when matches were last modified.

## Root Cause
1. No database trigger existed to automatically update `updated_at` timestamps
2. The application wasn't explicitly setting `updated_at` in PATCH requests
3. Bonus issue found: Database constraint didn't allow 'tbd' and 'completed' statuses that the application uses

## Solution
This migration implements the industry-standard approach:
- Uses PostgreSQL's `moddatetime` extension for automatic timestamp updates
- Fixes the `match_status` constraint to allow all statuses used by the application
- Adds clear documentation about the automatic behavior

## How to Apply

### Option 1: Supabase Dashboard (Recommended)
1. Log into Supabase Dashboard: https://supabase.com/dashboard
2. Select your project
3. Go to **SQL Editor**
4. Click **New Query**
5. Copy and paste the contents of `021_add_updated_at_trigger.sql`
6. Click **Run** (or press Cmd/Ctrl + Enter)
7. Verify success message appears

### Option 2: Supabase CLI
```bash
cd backend
supabase db push
```

### Option 3: Direct SQL (if you have psql access)
```bash
psql <your-connection-string> < backend/supabase/migrations/021_add_updated_at_trigger.sql
```

## Verification

After applying the migration, verify it's working:

### 1. Check the trigger exists
```sql
SELECT
  trigger_name,
  event_manipulation,
  event_object_table
FROM information_schema.triggers
WHERE trigger_name = 'handle_updated_at';
```

Expected result:
```
trigger_name      | event_manipulation | event_object_table
------------------|--------------------|-----------------
handle_updated_at | UPDATE             | matches
```

### 2. Test with a manual update
```sql
-- Get a match to test
SELECT id, home_score, away_score, updated_at
FROM matches
LIMIT 1;

-- Update it (change the ID to match your test record)
UPDATE matches
SET home_score = home_score + 1
WHERE id = <your-test-id>;

-- Check the updated_at changed
SELECT id, home_score, away_score, updated_at
FROM matches
WHERE id = <your-test-id>;
```

The `updated_at` should now show the current timestamp!

### 3. Wait for next scraper run
The match-scraper runs daily at 6 AM UTC. After the next run:
1. Check the UI for a match that was updated
2. The "Last Updated" field should now show the current date/time

## Rollback (if needed)

If you need to rollback this migration:

```sql
-- Remove the trigger
DROP TRIGGER IF EXISTS handle_updated_at ON matches;

-- Restore old constraint (without tbd/completed)
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'played', 'postponed', 'cancelled'));
```

## Impact
- **Zero downtime**: This is a non-breaking change
- **Immediate effect**: All future updates will automatically update `updated_at`
- **No code changes needed**: The trigger works at the database level
- **Performance**: Negligible impact (triggers are very efficient)

## Related Files
- `/backend/celery_tasks/match_tasks.py` - Celery worker that updates matches
- `/backend/supabase/migrations/020_add_live_match_status.sql` - Previous status migration
- `/backend/supabase/migrations/013_add_game_status.sql` - Original status field

## Testing Log Reference
```
Match 99479 (Downtown United vs TSF Academy):
- Created: Oct 27, 2025, 6:52 PM
- Scores updated: Nov 9, 2025, 00:39:06 UTC ✓
- updated_at NOT updated (before this migration) ✗
- After this migration: updated_at will auto-update ✓
```
