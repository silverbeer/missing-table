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
# Production deploys via GitOps (ArgoCD watches values-doks.yaml)
# Manual helm commands for debugging only:
helm upgrade missing-table ./missing-table --namespace missing-table -f ./missing-table/values-doks.yaml
```

**Full deployment docs**: [docs/05-deployment/README.md](docs/05-deployment/README.md)

---

## Production Environment

**DOKS (DigitalOcean Kubernetes Service)** - Current production platform.

| Component | Details |
|-----------|---------|
| **Cluster** | DOKS managed by Terraform in [missingtable-platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap) |
| **GitOps** | ArgoCD watches `helm/missing-table/values-doks.yaml` |
| **Images** | GHCR (`ghcr.io/silverbeer/missing-table-backend/frontend`) |
| **Secrets** | External Secrets Operator → AWS Secrets Manager |
| **Domains** | missingtable.com, www.missingtable.com, api.missingtable.com |
| **Database** | Supabase (cloud-hosted) |

**CI/CD Flow**: Push to main → CI builds images → Updates `values-doks.yaml` → ArgoCD syncs to DOKS

**Historical note**: GKE was shut down 2025-12-07, migrated to DOKS December 2025.

---

## Version Management

**Claude creates all commits/PRs and decides version bumps.**

Format: `MAJOR.MINOR.PATCH.BUILD` (e.g., `1.0.1.147`)

| Position | When to Increment |
|----------|-------------------|
| MAJOR | Breaking changes (API breaks, schema migrations, rewrites) |
| MINOR | New features (new endpoints, UI features) |
| PATCH | Bug fixes, refactoring, small improvements |
| BUILD | Automatic (CI deployment) |

```bash
./scripts/version-bump.sh major|minor|patch
```

---

## Database/Supabase

**Full guide**: [docs/02-development/schema-migrations.md](docs/02-development/schema-migrations.md)

### Schema Structure

The database schema is consolidated into a single baseline migration:
- **`supabase-local/migrations/00000000000000_schema.sql`** — Complete schema (tables, functions, RLS policies, indexes)
- **`supabase-local/supabase/seed.sql`** — Reference data (age_groups, seasons, match_types, leagues, divisions)
- `supabase/migrations/` is a **symlink** to `supabase-local/migrations/` — one source of truth

New schema changes go in additional timestamped migration files (e.g., `20260201000000_add_foo.sql`).

### Quick Reference
```bash
# Full local DB setup from scratch (schema + seed + test users)
./scripts/setup-local-db.sh              # Without match data
./scripts/setup-local-db.sh --restore    # With match data from existing backup
./scripts/setup-local-db.sh --from-prod  # Backup from prod first, then restore locally (RECOMMENDED)

# Local Supabase
cd supabase-local && npx supabase start|stop|status

# Reset database (applies schema + seed)
cd supabase-local && npx supabase db reset

# Create new migration
cd supabase-local && npx supabase db diff -f add_new_feature

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
cd backend && APP_ENV=prod uv run python manage_users.py list
cd backend && APP_ENV=prod uv run python manage_users.py create --email user@example.com --role admin
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
`teams`, `matches`, `seasons`, `age_groups`, `divisions`, `match_types`, `team_match_types`, `user_profiles`

### API Routes
`/api/auth/*`, `/api/standings`, `/api/matches`, `/api/match-types`, `/api/teams`, `/api/admin/*`

### Authentication Flow
```
Frontend → Backend API → Supabase
```
Backend-centered auth resolves k8s networking issues. All Supabase credentials stay in backend.

---

## In-Progress Features

### RabbitMQ/Celery Messaging
**Status**: Phase 0 Complete | **Docs**: [docs/rabbitmq-celery/README.md](docs/rabbitmq-celery/README.md)

### CrewAI Testing System
**Status**: Phase 1 Complete (1/8 agents) | **Docs**: [crew_testing/README.md](crew_testing/README.md)

---

## Need More Information?

- **Getting Started**: [docs/01-getting-started/README.md](docs/01-getting-started/README.md)
- **Daily Workflow**: [docs/02-development/daily-workflow.md](docs/02-development/daily-workflow.md)
- **Architecture**: [docs/03-architecture/README.md](docs/03-architecture/README.md)
- **Complete Documentation**: [docs/README.md](docs/README.md)

---

**Last Updated**: 2026-01-30
