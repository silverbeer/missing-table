# Tom's Soccer Club API Test Suites Implementation Plan

> **Status**: Implemented
> **Branch**: `backend-testing-toms-soccer-club`
> **Last Updated**: 2025-12-15

## Implementation Summary

Both test suites have been implemented:

### Pytest Suite (tsc_a_ prefix)
- **Location**: `backend/tests/tsc/`
- **Fixtures**: `backend/tests/fixtures/tsc/`
- **API Client**: `backend/api_client/` (generic, reusable)

### Bruno Suite (tsc_b_ prefix)
- **Location**: `bruno/backend-api/tsc-journey/`
- **Environment**: `bruno/backend-api/environments/tsc.bru`

---

## Overview

Create two parallel API test suites for the Missing Table FastAPI backend:
1. **Bruno test suite** - Prepends `tsc_b_` to all created entities
2. **Pytest + requests test suite** - Prepends `tsc_a_` to all created entities

Both suites follow a "journey" pattern testing role-based access control across 5 user types.

---

## Configuration

| Setting | Value |
|---------|-------|
| Default URL | `http://localhost:8000` (configurable via `BASE_URL` env var) |
| Password Pattern | `{username}123!` (e.g., `tsc_b_admin123!`) |
| Bruno Prefix | `tsc_b_` |
| Pytest Prefix | `tsc_a_` |
| Cleanup | Configurable: `--skip-cleanup` to leave data for UI testing |

---

## Setup Instructions

Both test suites use a shared `.env.tsc` file for managing secrets. This keeps credentials out of git while providing a single configuration point.

### Step 1: Create .env.tsc File

```bash
# Copy the example file
cp backend/tests/tsc/.env.tsc.example backend/tests/tsc/.env.tsc

# Edit with your credentials
nano backend/tests/tsc/.env.tsc
```

**Contents of `.env.tsc`:**
```bash
# Existing admin credentials (used to create initial infrastructure)
TSC_EXISTING_ADMIN_USERNAME=tom
TSC_EXISTING_ADMIN_PASSWORD=tom123!

# API base URL (default: http://localhost:8000)
BASE_URL=http://localhost:8000

# TSC user passwords (pattern: {username}123!)
# These are used by Bruno tests (tsc_b_ prefix)
existing_admin_pass=tom123!
tsc_admin_pass=tsc_b_admin123!
club_manager_pass=tsc_b_club_mgr123!
team_manager_pass=tsc_b_team_mgr123!
player_pass=tsc_b_player123!
club_fan_pass=tsc_b_club_fan123!
team_fan_pass=tsc_b_team_fan123!
```

> **Note**: `.env.tsc` is gitignored. The example file `.env.tsc.example` is committed for reference.

### Step 2: Run Pytest Suite (tsc_a_ prefix)

Pytest automatically loads `.env.tsc` via `python-dotenv`:

```bash
cd backend && uv run pytest tests/tsc/ -v
```

The TSC user passwords are auto-generated using the pattern `{username}123!`:
- `tsc_a_admin` → `tsc_a_admin123!`
- `tsc_a_club_mgr` → `tsc_a_club_mgr123!`
- etc.

### Step 3: Run Bruno Suite (tsc_b_ prefix)

Use the wrapper script that loads `.env.tsc`:

```bash
# Run all phases including cleanup
./bruno/backend-api/tsc-journey/run-tsc.sh

# Skip cleanup (for UI testing)
./bruno/backend-api/tsc-journey/run-tsc.sh --skip-cleanup

# Run cleanup only (after UI testing)
./bruno/backend-api/tsc-journey/run-tsc.sh cleanup

# Run specific phase
./bruno/backend-api/tsc-journey/run-tsc.sh 00-admin-setup
```

**Alternative: Bruno GUI**
1. Open Bruno application
2. Load the `bruno/backend-api` collection
3. Go to **Environments** → select **tsc**
4. Click on **Secrets** tab
5. Set values from your `.env.tsc` file

---

## Test Journey Phases

```
Phase 0: Admin Setup     → Create season, age group, division, club, admin user,
                           send invite to club manager, create 2 teams,
                           create 2 matches, update scores

Phase 1: Club Manager    → Signup via invite, login, view club, create 2 teams,
                           send invite to team manager and club fan,
                           create 2 matches, update scores, edit profile

Phase 2: Team Manager    → Signup via invite, login, view teams,
                           send invite to player and fan,
                           create 2 matches, update scores, edit profile,
                           create and set a match LIVE

Phase 3: Player          → Signup via invite, login, view team,
                           edit profile, view schedule

Phase 4: Fan             → Signup via invite, login, view standings,
                           view matches, view LIVE match

Phase 99: Cleanup        → Delete all test entities in FK-safe order
                           (invites, matches, teams, club, users, reference data)
```

### Invite Flow Diagram

```
Admin (existing) ──creates invite──► Club Manager
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
              Team Manager                               Club Fan (→ Phase 4)
                    │
        ┌──────────┴──────────┐
        ▼                     ▼
     Player               Team Fan (→ Phase 4)
```

---

## Entities to Create

### Reference Data & Club

| Entity | Bruno Name | Pytest Name |
|--------|------------|-------------|
| Season | `tsc_b_test_season` | `tsc_a_test_season` |
| Age Group | `tsc_b_u18` | `tsc_a_u18` |
| Division | `tsc_b_division_1` | `tsc_a_division_1` |
| Club | `tsc_b_soccer_club` | `tsc_a_soccer_club` |
| Team 1 | `tsc_b_premier_team` | `tsc_a_premier_team` |
| Team 2 | `tsc_b_reserve_team` | `tsc_a_reserve_team` |

### Users (Created via Invite Flow)

| User | Username | Role | Invited By |
|------|----------|------|------------|
| Admin | `tsc_b_admin` / `tsc_a_admin` | admin | (direct signup) |
| Club Manager | `tsc_b_club_mgr` / `tsc_a_club_mgr` | club_manager | Admin |
| Team Manager | `tsc_b_team_mgr` / `tsc_a_team_mgr` | team_manager | Club Manager |
| Player | `tsc_b_player` / `tsc_a_player` | team_player | Team Manager |
| Club Fan | `tsc_b_club_fan` / `tsc_a_club_fan` | club_fan | Club Manager |
| Team Fan | `tsc_b_team_fan` / `tsc_a_team_fan` | team_fan | Team Manager |

### Invites (Tracked for Cleanup)

| Invite Type | Created By | For User |
|-------------|------------|----------|
| `club_manager` | Admin | Club Manager |
| `team_manager` | Club Manager | Team Manager |
| `club_fan` | Club Manager | Club Fan |
| `team_player` | Team Manager | Player |
| `team_fan` | Team Manager | Team Fan |

### Matches

| Match | Home Team | Away Team | Status |
|-------|-----------|-----------|--------|
| Match 1 (Admin) | Premier | Reserve | completed |
| Match 2 (Admin) | Reserve | Premier | completed |
| Match 3 (Club Mgr) | Premier | Reserve | completed |
| Match 4 (Club Mgr) | Reserve | Premier | completed |
| Match 5 (Team Mgr) | Premier | Reserve | completed |
| Match 6 (Team Mgr) | Reserve | Premier | **LIVE** |

---

## Directory Structure

### Generic API Client (Reusable)

```
backend/api_client/                   # NEW - Generic, reusable API client
├── __init__.py                       # Exports MissingTableClient
├── client.py                         # MissingTableClient class
├── auth.py                           # Authentication helpers
└── endpoints/                        # Endpoint-specific methods
    ├── __init__.py
    ├── matches.py                    # Match CRUD operations
    ├── teams.py                      # Team CRUD operations
    ├── clubs.py                      # Club CRUD operations
    ├── invites.py                    # Invite system operations
    └── reference_data.py             # Seasons, age groups, divisions
```

**Usage:** Can be imported by TSC tests, locust load tests, scripts, or any Python code:
```python
from api_client import MissingTableClient
client = MissingTableClient(base_url="http://localhost:8000")
client.login("username", "password")
matches = client.matches.list(season_id=1)
```

### Pytest Suite (TSC-Specific)

```
backend/tests/
├── fixtures/
│   └── tsc/                          # NEW - TSC-specific wrapper
│       ├── __init__.py
│       ├── config.py                 # Prefixes, passwords, entity names
│       ├── client.py                 # TSCClient (wraps MissingTableClient)
│       └── entities.py               # EntityRegistry for cleanup tracking
└── tsc/                              # NEW - TSC journey tests
    ├── __init__.py
    ├── conftest.py                   # Module-scoped fixtures
    ├── test_00_setup.py              # Admin creates infrastructure
    ├── test_01_club_manager.py       # Club manager journey
    ├── test_02_team_manager.py       # Team manager journey
    ├── test_03_player.py             # Player journey
    ├── test_04_fan.py                # Fan journey
    ├── test_99_cleanup.py            # Cleanup verification
    └── utils/
        ├── __init__.py
        └── cleanup.py                # Standalone cleanup script
```

### Bruno Suite

```
bruno/backend-api/
├── environments/
│   └── tsc.bru                       # NEW: TSC environment variables
└── tsc-journey/                      # NEW
    ├── folder.bru
    ├── 00-admin-setup/
    │   ├── 01-admin-login.bru        # Login as existing admin (tom)
    │   ├── 02-create-season.bru
    │   ├── 03-create-age-group.bru
    │   ├── 04-create-division.bru
    │   ├── 05-create-club.bru
    │   ├── 06-create-admin-user.bru  # Signup tsc_b_admin
    │   ├── 07-admin-login-new.bru    # Login as tsc_b_admin
    │   ├── 08-create-premier-team.bru
    │   ├── 09-create-reserve-team.bru
    │   ├── 10-create-match-1.bru
    │   ├── 11-create-match-2.bru
    │   ├── 12-update-match-scores.bru
    │   └── 13-create-club-mgr-invite.bru
    ├── 01-club-manager/
    │   ├── 01-validate-invite.bru
    │   ├── 02-signup-with-invite.bru
    │   ├── 03-login.bru
    │   ├── 04-view-club.bru
    │   ├── 05-create-team-3.bru      # Additional teams
    │   ├── 06-create-team-4.bru
    │   ├── 07-create-match-3.bru
    │   ├── 08-create-match-4.bru
    │   ├── 09-update-match-scores.bru
    │   ├── 10-edit-profile.bru
    │   ├── 11-create-team-mgr-invite.bru
    │   └── 12-create-club-fan-invite.bru
    ├── 02-team-manager/
    │   ├── 01-validate-invite.bru
    │   ├── 02-signup-with-invite.bru
    │   ├── 03-login.bru
    │   ├── 04-view-teams.bru
    │   ├── 05-create-match-5.bru
    │   ├── 06-create-match-6.bru
    │   ├── 07-update-match-5-score.bru
    │   ├── 08-set-match-6-live.bru   # Set match status to 'live'
    │   ├── 09-edit-profile.bru
    │   ├── 10-create-player-invite.bru
    │   └── 11-create-team-fan-invite.bru
    ├── 03-player/
    │   ├── 01-validate-invite.bru
    │   ├── 02-signup-with-invite.bru
    │   ├── 03-login.bru
    │   ├── 04-view-team.bru
    │   ├── 05-edit-profile.bru
    │   └── 06-view-schedule.bru
    ├── 04-fan/
    │   ├── 01-validate-club-fan-invite.bru
    │   ├── 02-signup-club-fan.bru
    │   ├── 03-validate-team-fan-invite.bru
    │   ├── 04-signup-team-fan.bru
    │   ├── 05-login-club-fan.bru
    │   ├── 06-view-standings.bru
    │   ├── 07-view-matches.bru
    │   └── 08-view-live-match.bru    # View match with status='live'
    └── 99-cleanup/
        ├── 01-admin-login.bru
        ├── 02-delete-matches.bru     # Delete all 6 matches
        ├── 03-delete-teams.bru       # Delete all teams
        ├── 04-delete-club.bru
        ├── 05-cancel-invites.bru     # Cancel any pending invites
        ├── 06-delete-division.bru
        ├── 07-delete-age-group.bru
        └── 08-delete-season.bru
```

---

## Files to Create

### Generic API Client (10 files)

1. `backend/api_client/__init__.py` - Exports MissingTableClient
2. `backend/api_client/client.py` - Main MissingTableClient class
3. `backend/api_client/auth.py` - Authentication helpers (login, token management)
4. `backend/api_client/endpoints/__init__.py`
5. `backend/api_client/endpoints/matches.py` - Match CRUD operations
6. `backend/api_client/endpoints/teams.py` - Team CRUD operations
7. `backend/api_client/endpoints/clubs.py` - Club CRUD operations
8. `backend/api_client/endpoints/invites.py` - Invite system operations
9. `backend/api_client/endpoints/reference_data.py` - Seasons, age groups, divisions
10. `backend/api_client/endpoints/auth.py` - Auth endpoints (signup, profile)

### TSC Test Suite (14 files)

1. `backend/tests/fixtures/tsc/__init__.py`
2. `backend/tests/fixtures/tsc/config.py` - Prefixes, passwords, entity names
3. `backend/tests/fixtures/tsc/client.py` - TSCClient (wraps MissingTableClient, adds tracking)
4. `backend/tests/fixtures/tsc/entities.py` - EntityRegistry dataclass
5. `backend/tests/tsc/__init__.py`
6. `backend/tests/tsc/conftest.py` - Module fixtures
7. `backend/tests/tsc/test_00_admin_setup.py` - Admin setup + invite to club mgr
8. `backend/tests/tsc/test_01_club_manager.py` - Club manager journey + invites
9. `backend/tests/tsc/test_02_team_manager.py` - Team manager + live match
10. `backend/tests/tsc/test_03_player.py` - Player journey
11. `backend/tests/tsc/test_04_fan.py` - Fan journey + view live match
12. `backend/tests/tsc/test_99_cleanup.py` - Cleanup tests
13. `backend/tests/tsc/utils/__init__.py`
14. `backend/tests/tsc/utils/cleanup.py` - Standalone cleanup script

### Bruno Files (~55 files)

1. `bruno/backend-api/environments/tsc.bru` - Environment variables
2. `bruno/backend-api/tsc-journey/folder.bru`
3. 00-admin-setup folder: 13 .bru files
4. 01-club-manager folder: 12 .bru files
5. 02-team-manager folder: 11 .bru files
6. 03-player folder: 6 .bru files
7. 04-fan folder: 8 .bru files
8. 99-cleanup folder: 8 .bru files

---

## Implementation Order

### Step 1: Pytest Foundation
- Create `fixtures/tsc/` directory and `__init__.py` files
- Implement `config.py` with all constants
- Implement `api_client.py` with TSCApiClient class
- Create `tsc/conftest.py` with fixtures

### Step 2: Pytest Test Files
- Implement `test_00_setup.py` (admin creates infrastructure)
- Implement `test_01_club_manager.py`
- Implement `test_02_team_manager.py`
- Implement `test_03_player.py`
- Implement `test_04_fan.py`

### Step 3: Pytest Cleanup
- Implement `test_99_cleanup.py`
- Implement `utils/cleanup.py` standalone script
- Test cleanup idempotency

### Step 4: Bruno Environment
- Create `tsc.bru` environment file
- Create folder structure

### Step 5: Bruno Setup Phase
- Create `00-setup/` folder and all .bru files
- Test admin login and entity creation

### Step 6: Bruno Journey Phases
- Create `01-club-manager/` folder and files
- Create `02-team-manager/` folder and files
- Create `03-player/` folder and files
- Create `04-fan/` folder and files

### Step 7: Bruno Cleanup
- Create `99-cleanup/` folder and files
- Ensure FK-safe deletion order

### Step 8: Documentation
- Update `docs/04-testing/README.md` with TSC suite info
- Add run instructions to test files

---

## Cleanup Strategy (FK-Safe Order)

```
1. Matches      (depends on teams, seasons, age_groups)
2. Teams        (depends on clubs, divisions, age_groups)
3. Club         (no dependencies after teams gone)
4. Invites      (cancel any pending invites - no FK deps)
5. Division     (no dependencies after teams gone)
6. Age Group    (no dependencies after teams gone)
7. Season       (no dependencies after matches gone)
8. Users        (users created via invite may remain - manual cleanup)
```

**Note on User Cleanup:** Users created via invites (club_mgr, team_mgr, player, fans)
are identified by the `tsc_a_` or `tsc_b_` prefix in their username and can be
manually cleaned up by an admin if needed. The test suite does not automatically
delete users to avoid potential issues with Supabase Auth.

---

## Run Commands

### Pytest

```bash
# Full suite with auto-cleanup (default)
cd backend && uv run pytest tests/tsc/ -v --order-dependencies

# Journey WITHOUT cleanup (for UI testing afterwards)
cd backend && uv run pytest tests/tsc/ -v --order-dependencies --skip-cleanup
# OR exclude cleanup tests explicitly:
cd backend && uv run pytest tests/tsc/ -v --ignore=tests/tsc/test_99_cleanup.py

# Specific phase
cd backend && uv run pytest tests/tsc/test_00_setup.py -v

# Cleanup only (run after UI testing is done)
cd backend && uv run pytest tests/tsc/test_99_cleanup.py -v

# Different environment
BASE_URL=https://dev.missingtable.com uv run pytest tests/tsc/ -v

# Manual cleanup script (alternative to running cleanup tests)
cd backend && uv run python -m tests.tsc.utils.cleanup --prefix tsc_a_
```

### Bruno

```bash
# Using the wrapper script (recommended - loads .env.tsc automatically)
./bruno/backend-api/tsc-journey/run-tsc.sh                    # Full journey with cleanup
./bruno/backend-api/tsc-journey/run-tsc.sh --skip-cleanup     # Skip cleanup for UI testing
./bruno/backend-api/tsc-journey/run-tsc.sh cleanup            # Cleanup only
./bruno/backend-api/tsc-journey/run-tsc.sh 00-admin-setup     # Run specific phase

# Direct bru CLI (requires manual secret setup or env vars)
bru run bruno/backend-api/tsc-journey --env tsc

# Different environment (edit BASE_URL in .env.tsc or override)
BASE_URL=https://dev.missingtable.com ./bruno/backend-api/tsc-journey/run-tsc.sh
```

### Typical UI Testing Workflow

**Using Pytest (tsc_a_ prefix):**
```bash
# Step 1: Run journey tests (skip cleanup)
cd backend && uv run pytest tests/tsc/ -v --ignore=tests/tsc/test_99_cleanup.py

# Step 2: Do your manual UI testing in browser...
# Test data is available: tsc_a_soccer_club, tsc_a_premier_team, etc.
# Login with: tsc_a_admin / tsc_a_admin123!

# Step 3: When done, run cleanup
cd backend && uv run pytest tests/tsc/test_99_cleanup.py -v
```

**Using Bruno (tsc_b_ prefix):**
```bash
# Step 1: Run journey tests (skip cleanup)
./bruno/backend-api/tsc-journey/run-tsc.sh --skip-cleanup

# Step 2: Do your manual UI testing in browser...
# Test data is available: tsc_b_soccer_club, tsc_b_premier_team, etc.
# Login with: tsc_b_admin / tsc_b_admin123!

# Step 3: When done, run cleanup
./bruno/backend-api/tsc-journey/run-tsc.sh cleanup
```

---

## Key API Endpoints Used

### Authentication & Profile

| Phase | Endpoint | Method | Description |
|-------|----------|--------|-------------|
| All | `/api/auth/login` | POST | Login with username/password |
| All | `/api/auth/signup` | POST | Signup (with optional invite_code) |
| All | `/api/auth/profile` | GET | Get current user profile |
| All | `/api/auth/profile` | PUT | Update profile |

### Invite System

| Phase | Endpoint | Method | Description |
|-------|----------|--------|-------------|
| Setup | `/api/invites/admin/club-manager` | POST | Admin creates club manager invite |
| Club Mgr | `/api/invites/validate/{code}` | GET | Validate invite before signup |
| Club Mgr | `/api/invites/club-manager/club-fan` | POST | Create club fan invite |
| Club Mgr | `/api/invites/admin/team-manager` | POST | Create team manager invite |
| Team Mgr | `/api/invites/team-manager/team-player` | POST | Create player invite |
| Team Mgr | `/api/invites/team-manager/team-fan` | POST | Create team fan invite |
| Cleanup | `/api/invites/{id}` | DELETE | Cancel pending invites |

### Reference Data (Admin)

| Phase | Endpoint | Method |
|-------|----------|--------|
| Setup | `/api/seasons` | POST |
| Setup | `/api/age-groups` | POST |
| Setup | `/api/divisions` | POST |
| Setup | `/api/clubs` | POST |
| Cleanup | `/api/seasons/{id}` | DELETE |
| Cleanup | `/api/age-groups/{id}` | DELETE |
| Cleanup | `/api/divisions/{id}` | DELETE |
| Cleanup | `/api/clubs/{id}` | DELETE |

### Teams

| Phase | Endpoint | Method |
|-------|----------|--------|
| Setup/Club Mgr | `/api/teams` | POST |
| Team Mgr | `/api/teams` | GET |
| Cleanup | `/api/teams/{id}` | DELETE |

### Matches

| Phase | Endpoint | Method | Description |
|-------|----------|--------|-------------|
| Setup/Club Mgr/Team Mgr | `/api/matches` | POST | Create match |
| All | `/api/matches` | GET | List matches (with filters) |
| Team Mgr | `/api/matches/{id}` | PATCH | Update score, set status='live' |
| Fan | `/api/matches?status=live` | GET | View live matches |
| Cleanup | `/api/matches/{id}` | DELETE | Delete match |

### Standings

| Phase | Endpoint | Method |
|-------|----------|--------|
| Fan | `/api/table` | GET |

---

## Dependencies

### Pytest
- `requests` (already installed)
- `pytest-order` (for test ordering) - may need to add

### Bruno
- Bruno CLI: `npm install -g @usebruno/cli`

---

## Notes

- Tests create unique entities with prefixes to avoid conflicts with real data
- Cleanup is idempotent - safe to run multiple times
- User cleanup may be skipped (users with tsc_ prefix can be manually removed)
- Both suites can run against production safely due to prefix isolation
- **Skip cleanup workflow**: Run journey tests, do UI testing manually, then run cleanup separately
- Entity IDs are stored in `entity_registry` (pytest) and environment vars (Bruno) between runs

---

## Review Comments

<!-- Add your comments below this line -->


