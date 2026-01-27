# API Client Architecture

## Overview

`MissingTableClient` (`backend/api_client/client.py`) is a type-safe HTTP client that wraps every backend API endpoint. It provides:

- Full type safety via Pydantic models
- Automatic authentication handling (JWT bearer tokens)
- Retry logic with exponential backoff
- Request/response logging
- Structured error handling with typed exceptions

## Rule: Every Endpoint Needs a Client Method + Contract Test

**Every non-excluded API endpoint MUST have:**
1. A method in `MissingTableClient`
2. At least one contract test in `tests/contract/`

This is enforced by the CI gate (`tests/test_api_client_coverage.py`).

## How to Add a New Endpoint

1. **Add the route** to `app.py` (or an API router file)
2. **Add a method** to `api_client/client.py` following the existing pattern
3. **Add a contract test** to `tests/contract/test_<domain>_contract.py`
4. **Regenerate the inventory**: `cd backend && uv run python scripts/generate_api_inventory.py`
5. **Commit** `api_inventory.json` alongside your changes

The CI coverage test will fail if any step is missed. The GenAI PR workflow will suggest implementations if you forget.

## Architecture

```
MissingTableClient          (reusable, production-grade)
    |
    +-- TSCClient            (test wrapper, adds entity tracking)
    |       |
    |       +-- TSC tests    (journey/integration tests)
    |
    +-- Contract tests       (validate response structure)
    |
    +-- Any future consumer  (scripts, CLI tools, etc.)
```

### MissingTableClient

The base client in `api_client/client.py`. Methods follow this pattern:

```python
def get_team_roster(self, team_id: int, season_id: int | None = None) -> dict[str, Any]:
    """Get team roster for a season."""
    params = {}
    if season_id is not None:
        params["season_id"] = season_id
    response = self._request("GET", f"/api/teams/{team_id}/roster", params=params or None)
    return response.json()
```

For file uploads, use `_request_multipart`:

```python
def upload_club_logo(self, club_id: int, file_path: str) -> dict[str, Any]:
    """Upload a club logo (multipart)."""
    with open(file_path, "rb") as f:
        response = self._request_multipart(
            "POST", f"/api/clubs/{club_id}/logo",
            files={"file": (file_path.split("/")[-1], f)},
        )
    return response.json()
```

### TSCClient

`tests/fixtures/tsc/client.py` wraps `MissingTableClient` with:
- Entity tracking (auto-cleanup after tests)
- Idempotent get-or-create operations
- TSC-specific convenience methods

TSCClient delegates to typed `MissingTableClient` methods instead of raw HTTP calls.

## Test Inventory

`backend/api_inventory.json` maps every endpoint to its client method and test coverage.

### Format

Each endpoint entry:
```json
{
  "method": "GET",
  "path": "/api/teams/{team_id}/roster",
  "client_method": "get_team_roster",
  "client_file": "api_client/client.py",
  "tests": [
    {"file": "tests/contract/test_teams_contract.py", "test_name": "test_get_team_roster", "type": "contract"}
  ],
  "coverage_status": "fully_covered"
}
```

### Coverage statuses

| Status | Meaning | CI result |
|--------|---------|-----------|
| `fully_covered` | Has client method + contract test | Pass |
| `client_only` | Has client method, no contract test | **Fail** |
| `missing_client` | No client method | **Fail** |
| `excluded` | Intentionally excluded (with reason) | Pass |

### Regenerating

```bash
cd backend && uv run python scripts/generate_api_inventory.py
```

This introspects FastAPI routes, parses `client.py` AST, and scans test files.

## CI Gate

`tests/test_api_client_coverage.py` validates:

1. Every FastAPI route is in the inventory (or excluded)
2. Every inventory endpoint has a `client_method`
3. Every inventory endpoint has at least 1 contract test
4. No stale inventory entries (no orphaned entries)
5. Every excluded endpoint has a documented reason

Run locally:
```bash
cd backend && uv run pytest tests/test_api_client_coverage.py -v
```

## GenAI PR Workflow

`.github/workflows/api-coverage-review.yml` triggers on PRs that modify route files. It:

1. Regenerates the inventory and checks for drift
2. Summarizes coverage gaps
3. (If `ANTHROPIC_API_KEY` is set) Uses Claude to analyze the diff and suggest client methods + contract tests

The GenAI step is advisory (non-blocking). The CI gate is the hard blocker.

## Excluded Endpoints

Some endpoints are intentionally excluded from the client:

| Endpoint | Reason |
|----------|--------|
| `POST /api/auth/oauth/callback` | Browser redirect flow |
| `POST /api/match-scraper/matches` | Internal scraper ingestion |
| `GET /api/check-match` | Internal scraper duplicate-check |

These are documented in `api_inventory.json` under `excluded_endpoints`.
