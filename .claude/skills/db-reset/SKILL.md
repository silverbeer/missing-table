---
name: db-reset
description: Reset local Supabase database with schema, migrations, seed data, and test users. Use when you need a fresh local database.
allowed-tools: Bash
---

# Local Database Reset

Reset the local Supabase database to a clean state with all migrations applied and test users created.

## CRITICAL: Local Only Safety Check

**BEFORE running any reset command, ALWAYS verify the environment is set to local:**

```bash
cd /Users/silverbeer/gitrepos/missing-table && ./switch-env.sh status 2>&1 | grep -A1 "Supabase:"
```

**Expected output must show `local`:**
```
Supabase:
  Source: local
```

**If it shows `prod`, STOP and DO NOT proceed.** Inform the user that the environment is set to production and they must switch to local first:
```bash
./switch-env.sh supabase local
```

## The Commands

**Step 1: Run the setup script:**
```bash
cd /Users/silverbeer/gitrepos/missing-table && ./scripts/setup-local-db.sh --from-prod
```

**Step 2: Reset PostgreSQL sequences (REQUIRED after data restore):**
```bash
# pragma: allowlist secret (local dev database only)
PGPASSWORD=postgres psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -c "
SELECT setval(pg_get_serial_sequence('public.matches', 'id'), COALESCE((SELECT MAX(id) FROM public.matches), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.teams', 'id'), COALESCE((SELECT MAX(id) FROM public.teams), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.playoff_bracket_slots', 'id'), COALESCE((SELECT MAX(id) FROM public.playoff_bracket_slots), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.leagues', 'id'), COALESCE((SELECT MAX(id) FROM public.leagues), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.divisions', 'id'), COALESCE((SELECT MAX(id) FROM public.divisions), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.seasons', 'id'), COALESCE((SELECT MAX(id) FROM public.seasons), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.age_groups', 'id'), COALESCE((SELECT MAX(id) FROM public.age_groups), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('public.clubs', 'id'), COALESCE((SELECT MAX(id) FROM public.clubs), 0) + 1, false);
"
```

**Why sequences must be reset:** After restoring data from backup, PostgreSQL sequences still start at 1. Without resetting, INSERT operations fail with "duplicate key" errors.

This does everything:
1. Resets database (schema + migrations + seed)
2. Backs up fresh data from production
3. Restores all data to local (teams, matches, leagues, etc.)
4. Flushes Redis cache (clears stale cached data)
5. Syncs users from prod with role-based passwords
6. Seeds test users (tom, tom_ifa, tom_ifa_fan, tom_club)
7. Resets PostgreSQL sequences to avoid duplicate key errors

**NEVER use `supabase db reset` directly** — it skips data restore, Redis flush, sequence reset, and user setup.

## Test Users

After reset, these users are available:

| Username | Password | Role |
|----------|----------|------|
| tom | admin123 | admin |
| tom_ifa | team123 | team-manager |
| tom_ifa_fan | fan123 | team-fan |
| tom_club | club123 | club_manager |

## Prerequisites

Local Supabase must be running:
```bash
cd /Users/silverbeer/gitrepos/missing-table/supabase-local && npx supabase status
```

If not running:
```bash
cd /Users/silverbeer/gitrepos/missing-table/supabase-local && npx supabase start
```

## Workflow

1. **FIRST: Verify environment is LOCAL** (see safety check above) — STOP if prod
2. Ensure local Supabase is running
3. Run: `./scripts/setup-local-db.sh --from-prod`
4. Wait for completion (backs up prod, restores data, flushes Redis, seeds users)
5. Run the sequence reset SQL command (Step 2 above)
6. Inform user when complete and remind them of test credentials

## Verification

After reset, verify users exist:
```bash
cd /Users/silverbeer/gitrepos/missing-table/backend && uv run python scripts/manage_users.py list
```
