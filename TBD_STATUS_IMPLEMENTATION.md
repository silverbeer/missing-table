# TBD Match Status Implementation Summary

**Branch:** `feature/support-tbd-match-status`
**Date:** 2025-10-19
**Status:** ✅ Complete - Ready for Testing

## Overview

Added support for "tbd" (to be determined) match status to handle matches that have been played but scores are not yet available from the source system (mlssoccer.com).

## Changes Made

### 1. Pydantic Model ✅
**File:** `backend/models/match_data.py`

```python
status: Literal["scheduled", "tbd", "completed", "postponed", "cancelled"] | None
```

- Added "tbd" to status Literal type
- Updated description: "Match status (tbd = match played, score pending)"

### 2. JSON Schema Contract ✅
**File:** `docs/08-integrations/match-message-schema.json`

- Version: `1.0.0` → `1.1.0`
- Added "tbd" to status enum
- Updated description with tbd explanation
- Added example with tbd status

### 3. Celery Worker Logic ✅
**File:** `backend/celery_tasks/match_tasks.py`

Enhanced `_check_needs_update()` docstring to document status transitions:
```
- scheduled → tbd: Match played, awaiting score
- tbd → tbd: No change (skip)
- tbd → completed: Score posted (update with scores)
- scheduled → completed: Direct completion (skip tbd)
```

Worker already handles these transitions correctly via existing logic.

### 4. Validation Tasks ✅
**File:** `backend/celery_tasks/validation_tasks.py`

```python
valid_statuses = ['scheduled', 'tbd', 'live', 'completed', 'cancelled', 'postponed']
```

Added "tbd" to valid statuses list.

### 5. Database Migration ✅
**File:** `supabase/migrations/20251019000020_add_tbd_match_status.sql`

- Drops existing CHECK constraint
- Adds new constraint with 'tbd' included
- Creates index for tbd status queries (performance)
- Updates column comments

**Migration SQL:**
```sql
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'tbd', 'live', 'completed', 'postponed', 'cancelled'));
```

### 6. Tests ✅
**File:** `backend/tests/contract/test_games_contract.py`

```python
valid_statuses = ["scheduled", "tbd", "played", "postponed", "cancelled", "completed"]
```

Updated contract tests to accept "tbd" as valid status.

## Status Transition Flow

```
┌──────────────┐
│  scheduled   │  ← Match created, future date
└──────┬───────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌──────────┐      ┌────────────┐
│   tbd    │      │ completed  │  ← Direct completion (score available)
└────┬─────┘      └────────────┘
     │
     │ (score posted)
     │
     ▼
┌────────────┐
│ completed  │
└────────────┘
```

## Deployment Steps

### 1. Apply Database Migration

```bash
# Switch to dev environment
./switch-env.sh dev

# Apply migration
npx supabase db push

# Or via Supabase dashboard:
# - Go to SQL Editor
# - Run migration script
```

### 2. Rebuild and Deploy Workers

```bash
# Rebuild worker image
./k3s/worker/rebuild-and-deploy.sh

# Verify workers are running
kubectl get pods -n match-scraper -l app=missing-table-worker

# Check logs
kubectl logs -n match-scraper -l app=missing-table-worker -f
```

### 3. Verify Schema Changes

```bash
# Check Pydantic validation
cd backend
uv run python -c "from models.match_data import MatchData; print(MatchData(home_team='A', away_team='B', date='2025-10-20', season='2024-25', age_group='U14', match_type='League', status='tbd'))"

# Expected: No validation errors
```

## Testing Plan

### Phase 1: Unit Tests
```bash
cd backend
uv run pytest tests/contract/test_games_contract.py::TestGamesContract::test_game_status_values -v
```

### Phase 2: Integration Testing
1. **Match-scraper sends tbd status:**
   - Deploy match-scraper with tbd support
   - Trigger scrape of matches with "TBD" on mlssoccer.com
   - Verify messages reach queue

2. **Workers process tbd messages:**
   ```bash
   # Monitor worker logs
   kubectl logs -n match-scraper -l app=missing-table-worker -f

   # Check RabbitMQ queue
   kubectl exec -n match-scraper rabbitmq-0 -- rabbitmqctl list_queues
   ```

3. **Database stores tbd status:**
   - Check Supabase for matches with status='tbd'
   - Verify no validation errors in worker logs

### Phase 3: Status Transition Testing
1. Create test match with status='scheduled'
2. Update to status='tbd' (match played, no score)
3. Update to status='completed' with scores
4. Verify each transition persists correctly

## Verification Checklist

- [x] MatchData model accepts "tbd" status
- [x] JSON schema includes "tbd" in enum
- [x] Validation task accepts "tbd"
- [x] Database migration created
- [x] Tests updated
- [x] Worker logic documented
- [ ] Database migration applied (dev)
- [ ] Database migration applied (prod)
- [ ] Workers deployed with changes
- [ ] End-to-end test with match-scraper
- [ ] Status transitions verified

## Rollback Plan

If issues occur:

### 1. Revert Database Changes
```sql
-- Remove tbd from constraint
ALTER TABLE matches
DROP CONSTRAINT IF EXISTS matches_match_status_check;

ALTER TABLE matches
ADD CONSTRAINT matches_match_status_check
CHECK (match_status IN ('scheduled', 'live', 'completed', 'postponed', 'cancelled'));
```

### 2. Revert Code Changes
```bash
# Switch back to main
git checkout main

# Rebuild workers
./k3s/worker/rebuild-and-deploy.sh
```

## Files Changed

```
M  backend/celery_tasks/match_tasks.py           (Enhanced documentation)
M  backend/celery_tasks/validation_tasks.py      (Added 'tbd' to valid statuses)
M  backend/models/match_data.py                  (Added 'tbd' to Literal type)
M  backend/tests/contract/test_games_contract.py (Added 'tbd' to test)
M  docs/08-integrations/match-message-schema.json (Schema v1.1.0, added 'tbd')
A  supabase/migrations/20251019000020_add_tbd_match_status.sql (New migration)
```

## Next Steps

1. **Coordinate with match-scraper team:**
   - Confirm match-scraper tbd implementation is complete
   - Align on deployment timing

2. **Deploy to dev environment:**
   - Apply database migration
   - Deploy updated workers
   - Run end-to-end test

3. **Monitor dev for 24-48 hours:**
   - Check for validation errors
   - Verify tbd → completed transitions
   - Confirm no performance issues

4. **Deploy to production:**
   - Apply migration during low-traffic window
   - Deploy workers with zero-downtime rolling update
   - Monitor logs for first hour

## Questions or Issues?

- **Schema questions:** See `docs/08-integrations/match-message-schema.json`
- **Worker logs:** `kubectl logs -n match-scraper -l app=missing-table-worker -f`
- **Database:** Supabase dashboard or `npx supabase db diff`
- **Tests:** `cd backend && uv run pytest tests/contract/ -v`

---

**Implementation Complete:** Ready for deployment and testing ✅
