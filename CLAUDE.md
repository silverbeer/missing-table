# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation First!

**CRITICAL**: When making changes, ALWAYS update relevant documentation in `docs/`.

### Documentation Structure

- **[docs/README.md](docs/README.md)** - Master documentation hub (start here!)
- **[docs/01-getting-started/](docs/01-getting-started/)** - Setup and first contribution
- **[docs/02-development/](docs/02-development/)** - Daily workflows
- **[docs/03-architecture/](docs/03-architecture/)** - System design
- **[docs/04-testing/](docs/04-testing/)** - Testing strategy
- **[docs/05-deployment/](docs/05-deployment/)** - Deployment guides
- **[docs/06-security/](docs/06-security/)** - Security practices
- **[docs/07-operations/](docs/07-operations/)** - Operations and maintenance

**Remember**: Outdated docs are worse than no docs. Keep them current!

---

## Terminology

- **MT** = missingtable.com (project shorthand)
- **MT backend** = FastAPI backend (Python 3.13+, located in `backend/`)
- **MT frontend** = Vue.js application (located in `frontend/`)
- **MT scraper** = match-scraper repository (separate repo)
- **MT db** = Supabase databases (local/prod environments)

---

## CRITICAL: Git Workflow - Protected Main Branch

**NEVER COMMIT DIRECTLY TO MAIN** - The `main` branch is **PROTECTED** and requires Pull Requests.

### Before Starting Any New Feature

**ALWAYS check your current branch status before beginning work:**

```bash
git status
git branch --show-current
```

If you're on an old feature branch with uncommitted changes:
1. Commit or stash those changes first
2. Create a PR if needed
3. Then create a fresh feature branch from main

**Do NOT start new work on an existing feature branch** - this leads to mixed changes that are hard to separate.

### Standard Workflow

```bash
# 1. Create feature branch
git checkout main && git pull origin main
git checkout -b feature/your-feature-name

# 2. Commit to feature branch
git add <files> && git commit -m "feat: your commit message"

# 3. Push and create PR
git push origin feature/your-feature-name
# Create PR at: https://github.com/silverbeer/missing-table/pulls

# 4. After merge, cleanup
git checkout main && git pull origin main
git branch -d feature/your-feature-name
```

---

## CRITICAL: What NOT to Commit

**NEVER commit debug/test/temporary scripts:**
- `backend/check_*.py`, `backend/test_*.py`, `backend/debug_*.py`, `backend/fix_*.py`
- `fix_*.sql`, `temp_*.sql`, `scratch.*`, `notes.*`
- Exception: `backend/tests/test_*.py` (pytest tests) SHOULD be committed

**Always verify before commit:** `git diff --staged --name-only | grep -E "(check_|test_|debug_|fix_)"`

---

## Code Quality & Linting

```bash
# Frontend (Vue/JavaScript)
cd frontend && npm run lint

# Backend (Python)
cd backend && uv run ruff check .
```

Always run linters before committing changes.

---

## Writing Testable Code

**CRITICAL**: Do NOT write tests for untestable code. Refactor first.

If code mixes business logic with database queries, **STOP and communicate**:
1. Explain WHY the code is untestable
2. Propose refactoring to extract pure functions
3. Wait for approval before proceeding

| Code Type | Test Type | Approach |
|-----------|-----------|----------|
| Pure functions | Unit tests | Direct testing, no mocks |
| DAO methods | Integration tests | Real test database |
| API endpoints | Integration tests | Test client with test database |

---

## Project Overview

Full-stack web application for MLS Next sports league standings and match schedules.
- **Backend**: FastAPI (Python 3.13+) in `backend/`
- **Frontend**: Vue 3 in `frontend/`
- **Database**: Supabase (local/prod)

**Detailed docs**: [docs/03-architecture/README.md](docs/03-architecture/README.md)

---

## CRITICAL: Most Teams Have No User Data

**Absent user data is the normal state, not an error state.** Design every component for it.

MT holds two kinds of data, and they fail in opposite directions:

| Kind | Examples | Source | Coverage |
|------|----------|--------|----------|
| **System-generated** | match results, schedules, standings | MT scraper (MLS Next) | Every team, always |
| **User-generated** | rosters, players, live scores, goals, assists | club/team managers | **The exception, not the rule** |

A team exists in the database because the scraper created it, not because anyone signed up. So the
default team has a season of results and nothing else. Adoption is the product goal — recruiting
parents as team managers to build rosters, live-score matches, and record goals and assists — so
every screen is either recruiting a manager or serving one, and a screen that breaks without a
roster recruits nobody.

### The three states — design all three, never default into one

Every component that depends on user data handles:

| State | Meaning | What the UI does |
|-------|---------|------------------|
| **Unclaimed** | no manager has claimed this team | show scraped data + a claim call-to-action |
| **Claimed, empty** | manager exists, roster not built yet | show scraped data + a nudge to finish setup |
| **Populated** | roster and/or match events exist | the full experience |

These are distinct in the data model too: `null` (never provided) and `[]` (provided, empty) mean
different things and must not be collapsed. The difference is the adoption funnel — how many
claimed teams never finished a roster is the metric that tells us where onboarding fails.

A loading skeleton is not an empty state. It promises data that is not coming.

### Rules

1. **Missing user data is `200`, never `404`.** The team exists — the scraper made it. A 404 says
   otherwise, and it puts a routine, expected condition on the error path where it triggers
   retries, alerts, and monitoring noise.
2. **Never pun absent into zero.** "No goals recorded" ≠ "0 goals scored". A player page for an
   untracked team must not render `0 G / 0 A` — that is a measurement claim about someone nobody
   measured. Absent renders as absent (`—`, "not tracked"), and aggregates skip it rather than
   summing it as zero.
3. **Aggregates state their denominator.** A league-wide top-scorer list where 12% of teams log
   goals ranks *who tracks*, not who scores. Any cross-team statistic ships with its coverage
   ("from 9 of 74 teams reporting") or it does not ship.
4. **Degrade per field, not per page.** A team with a roster but no logged goals still shows the
   roster. One missing field never blanks a section, and never blanks a sibling section.
5. **Scraped data wins on results; user data wins on attribution.** When a manager's logged goals
   disagree with the scraped final score, the scraped score stands as the result and the user
   events stand as who did what. A manual entry never rewrites a scraped score, and a re-scrape
   never wipes goal attribution. Surface the disagreement rather than silently resolving it.
6. **Provenance is queryable.** Every record carries whether it came from the scraper or a user,
   and which user. Needed for the conflict rule above, for the audit trail on rosters of minors,
   and for coverage numbers.

### Testing

**The default fixture is a team with scraped matches and no user data.** Populated rosters are the
special case in tests because they are the special case in production. A test suite whose fixtures
all have full rosters proves nothing about the experience most visitors get.

Every component and endpoint that depends on user data needs a test per state above — including
the assertion that absent does not render as zero.

---

## Key Commands

### Service Management
```bash
./missing-table.sh dev      # Start with auto-reload (RECOMMENDED)
./missing-table.sh start    # Start both backend and frontend
./missing-table.sh stop     # Stop all services
./missing-table.sh status   # Show status and PIDs
./missing-table.sh tail     # Follow logs in real-time
```

### Individual Services
```bash
cd frontend && npm run serve           # Frontend only (localhost:8080)
cd backend && uv run python app.py     # Backend only (localhost:8000)
cd backend && uv run pytest            # Backend tests
cd frontend && npm run test:run        # Frontend tests
```

### Docker
```bash
# Images are built by CI and pushed to GHCR (GitHub Container Registry)
# Manual builds (local development only):
docker-compose up
docker-compose down
```

### Helm/Kubernetes
```bash
# Production deploys via GitOps (ArgoCD watches values-prod.yaml)
# Manual helm commands for debugging only:
helm upgrade missing-table ./missing-table --namespace missing-table -f ./missing-table/values-prod.yaml
```

**Full deployment docs**: [docs/05-deployment/README.md](docs/05-deployment/README.md)

---

## The `mt` CLI

A thin HTTP client over the API — live scoring and, since SB-672, read commands.
Answer a data question here before reaching for the database.

```bash
uv tool install --editable ./backend   # once; `mt` then works from anywhere
mt login                               # session expires; read commands say so
mt --env prod team matches "IFA U15"   # one command against prod; nothing persists
```

### Which environment a command targets

Precedence: **`--env` > `APP_ENV` > `.mt-config` > `local`** (SB-841). `mt config`
prints the resolved environment and which of those it came from, and any command
aimed anywhere but local announces itself before it runs.

`--env` changes nothing on disk. Editing `.mt-config` still works and still
redirects every later command in every shell — which is exactly why the flag
exists. Sessions are stored **per environment**, so logging in to prod does not
hand a prod token to a local command, and an active prod match is not confused
with a local one.

```bash
mt competitions                        # what -c accepts, and which qualify
mt team stats "IFA U15"                # the Golden Boot board
mt team stats "IFA U15" -c all         # every competition (default: League)
mt team matches "IFA U15"              # every competition (default), with status
mt team matches "IFA U15" -c Flex      # one competition
mt team matches "IFA U15" -c qualifying  # League + Flex — whatever is flagged
mt match show 1190                     # status, lineups, events
mt player stats 42
mt search --age U15 --days 30
mt match start 1053                    # live scoring: goal, message, halftime, end
mt team mapping list "NEFC"            # which age groups a team is registered in
mt team mapping add "NEFC" -a U16 -d Northeast
mt ingest failures                     # what the scraper could not resolve
mt ingest resolve 1 --note "fixed at the sender"
```

### Login

`mt login` looks for a password in this order, and stops at the first hit:

1. `TEST_USER_PASSWORD_<USER>` in `backend/.env.<env>` — local test users only;
   **`.env.prod` deliberately holds none**
2. `MT_PASSWORD` — for CI, where the value comes from a secret store
3. **1Password**, `op read op://agents/mt-<env>/credential`, overridable with
   `MT_OP_ITEM` or an `op_item` line in `.mt-config` (`{env}` and `{user}` are
   substituted)
4. an interactive prompt

With no terminal and no password source it refuses rather than prompting:
`getpass` cannot suppress echo without a TTY, so prompting there prints the
password and then fails anyway.

`mt login` targets whatever the rules above resolve to, and says so before it
reads a password.

**Never run `MT_PASSWORD=... mt login` from an agent shell** — the command line
is echoed into the session transcript, which is exactly how a secret becomes
permanent. Use 1Password, or a real terminal.

`-c` defaults differ on purpose: **stats default to League**, because a squad
total that folds friendlies in is not comparable with the league table beside
it; **matches default to every competition**, because a schedule that hides
fixtures is the surprise. `qualifying` is the union of the match types flagged
`counts_for_qualification` (SB-849) — read from the API, never a hardcoded list,
so the Matches chips, `mt` and the standings always agree.

A team's `age_groups` come **entirely** from `team_mappings`, and every
age-group team picker filters on that. A team with matches at an age group it
is not registered in is invisible there — which is why ingest now writes the
registration itself (SB-852). `mt team mapping` is the way to correct one by
hand.

**Only `live`, `completed` and `forfeit` matches count towards season stats**
(SB-671). `mt team matches` prints the status precisely so a "why is GP wrong"
question is one command, not a database session.

`STAT_FIELDS` and `took_part` in `mt_cli.py` mirror `GoldenBoot.vue`. Change one
and change the other — a stat that disagrees between CLI and web is worse than
one missing from either.

## Production Environment

**LKE (Linode Kubernetes Engine)** - Current production platform.

| Component | Details |
|-----------|---------|
| **Cluster** | LKE managed by Terraform in [missingtable-platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap) |
| **GitOps** | ArgoCD watches `helm/missing-table/values-prod.yaml` |
| **Images** | GHCR (`ghcr.io/silverbeer/missing-table-backend/frontend`) |
| **Secrets** | External Secrets Operator → AWS Secrets Manager |
| **Domains** | missingtable.com, www.missingtable.com, api.missingtable.com |
| **Database** | Supabase (cloud-hosted) |

**CI/CD Flow**: Push to main → CI builds images → Updates `values-prod.yaml` → ArgoCD syncs to LKE

**Historical note**: GKE shut down 2025-12-07, migrated to DOKS December 2025, migrated to LKE February 2026.

---

## Version Management

Format: `MAJOR.MINOR.PATCH.BUILD` (e.g., `1.3.1.1041`), shown in the app footer via `/api/version`.

- **`MAJOR.MINOR.PATCH`** lives in the `VERSION` file. Bumped automatically on merge to main by a **PR label gate** (CI job `update-helm-values` in `ci.yml`).
- **`BUILD`** = the CI workflow `run_number`, written to `values-prod.yaml` `buildId` on every deploy. Always increments; not tied to the label.

### PR label gate — pick one label per PR

| Label | Effect on merge | Use for |
|-------|-----------------|---------|
| `version:major` | MAJOR +1, reset MINOR/PATCH | Breaking changes (API breaks, schema rewrites) |
| `version:minor` | MINOR +1, reset PATCH | New features (endpoints, UI features) |
| `version:patch` | PATCH +1 | Bug fixes, refactors, small improvements |
| `version:none` | no MAJOR.MINOR.PATCH bump | Chore/infra/docs, image-tag commits |
| *(no label)* | **defaults to `version:patch`** | so the version always advances on a real merge |

CI reads the merged PR's label, runs `scripts/version-bump.sh <level>`, and commits the new `VERSION` alongside the image-tag update (`[skip ci]`). To switch the default from patch to "no bump", change the fallback `case` arm in `ci.yml`.

Manual bump (local, rarely needed): `./scripts/version-bump.sh major|minor|patch`

---

## Database/Supabase

**Full guide**: [docs/02-development/schema-migrations.md](docs/02-development/schema-migrations.md)

### Schema Structure

The database schema is consolidated into a single baseline migration:
- **`supabase/migrations/00000000000000_schema.sql`** — Complete schema (tables, functions, RLS policies, indexes)
- **`supabase/seed.sql`** — Reference data (age_groups, seasons, match_types, leagues, divisions)
- **`supabase/migrations/`** is the **one source of truth** for migrations (tracked in git). Standard Supabase CLI layout: run `npx supabase ...` from the repo root (SB-113 consolidated the old `supabase-local/` split).

### Local Ports (SB-113 convention)

Local Supabase uses the **553xx port block** so it can run alongside myrunstreak's stack (543xx defaults): API `55321`, DB `55322`, Studio `55323`, Mailpit `55324`, Analytics `55327`. Next repo gets 563xx.

New schema changes go in additional timestamped migration files (e.g., `20260201000000_add_foo.sql`).

### Quick Reference
```bash
# Full local DB setup from scratch (schema + seed + test users)
./scripts/setup-local-db.sh              # Without match data
./scripts/setup-local-db.sh --restore    # With match data from existing backup
./scripts/setup-local-db.sh --from-prod  # Backup from prod first, then restore locally (RECOMMENDED)

# Local Supabase
npx supabase start|stop|status

# Reset database (applies schema + seed)
npx supabase db reset

# Apply migrations locally (without reset)
./scripts/db_tools.sh migrate local

# Deploy migrations to production (backup → apply → verify)
./scripts/db_tools.sh migrate prod

# Create new migration
npx supabase db diff -f add_new_feature

# Backup/Restore
./scripts/db_tools.sh backup
./scripts/db_tools.sh restore
./scripts/db_tools.sh list
```

### Environment Switching
```bash
./switch-env.sh local    # Local Supabase (default)
./switch-env.sh prod     # Cloud production
./switch-env.sh status   # Check current environment
```

### User Management
```bash
cd backend && APP_ENV=prod uv run python scripts/manage_users.py list
cd backend && APP_ENV=prod uv run python scripts/manage_users.py create --email user@example.com --role admin
```

---

## Secret Management

Secrets are managed via Kubernetes Secrets - NEVER committed to git.

**Multi-layer protection:** pre-commit hooks (detect-secrets), GitHub Actions (gitleaks), .gitignore

**Docs**: [docs/SECRET_MANAGEMENT.md](docs/SECRET_MANAGEMENT.md)

---

## Architecture

### Backend (`backend/`)
- FastAPI application in `app.py`
- DAO pattern: `dao/enhanced_data_access_fixed.py`, `dao/supabase_data_access.py`
- Auth: `auth.py` (JWT, roles: admin, team_manager, user)
- Dependencies: `uv` + `pyproject.toml`

### Frontend (`frontend/`)
- Vue 3 + Composition API
- Key components: `LeagueTable.vue`, `ScoresSchedule.vue`, `AdminPanel.vue`
- State: `stores/`
- Styling: Tailwind CSS

### Database Tables
`teams`, `matches`, `seasons`, `age_groups`, `divisions`, `match_types`, `team_match_types`, `user_profiles`, `match_of_the_week`

### API Routes
`/api/auth/*`, `/api/standings`, `/api/matches`, `/api/match-types`, `/api/teams`, `/api/motw`, `/api/admin/*`

### Authentication Flow
```
Frontend → Backend API → Supabase
```
Backend-centered auth resolves k8s networking issues. All Supabase credentials stay in backend.

---

## In-Progress Features

### RabbitMQ/Celery Messaging
**Status**: Phase 0 Complete | **Docs**: [docs/rabbitmq-celery/README.md](docs/rabbitmq-celery/README.md)

### QE Plugin (Test Coverage & Generation)
Testing automation is handled by the [qe plugin](https://github.com/silverbeer/qe-plugin) (`/qe`, `/generate-tests`, `@qe-engineer`), configured via `.claude/qe.yml`. It replaced the retired CrewAI experiment — see [docs/04-testing/crewai-experiment-retrospective.md](docs/04-testing/crewai-experiment-retrospective.md) for lessons learned.

---

## Need More Information?

- **Getting Started**: [docs/01-getting-started/README.md](docs/01-getting-started/README.md)
- **Daily Workflow**: [docs/02-development/daily-workflow.md](docs/02-development/daily-workflow.md)
- **Architecture**: [docs/03-architecture/README.md](docs/03-architecture/README.md)
- **Complete Documentation**: [docs/README.md](docs/README.md)

---

**Last Updated**: 2026-08-16
