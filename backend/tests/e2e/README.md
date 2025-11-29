# E2E Tests

End-to-end tests for the Missing Table backend.

## Test Types

### API E2E Tests (Fast - ~5 seconds)
- `test_user_workflows.py` - User workflow and business logic tests
- `test_invite_workflow.py` - Invite system workflow tests

These tests use FastAPI's `TestClient` and run quickly without external dependencies.

**Run API E2E tests only:**
```bash
TEST_MODE=true uv run pytest tests/e2e/ -k "not playwright" -v --no-cov
```

### Playwright E2E Tests (Requires Frontend)
- `playwright/test_authentication.py` - Browser-based auth tests
- `playwright/test_standings.py` - Standings page tests
- `playwright/test_visual.py` - Visual regression tests

These tests require:
- Frontend running at `http://localhost:8080`
- Playwright browsers installed (`uv run playwright install`)

**Run Playwright tests:**
```bash
# Start frontend first, then:
TEST_MODE=true uv run pytest tests/e2e/playwright/ -v --no-cov
```

## Current Status

✅ **API E2E Tests: 31 passed, 2 skipped** (5.27s)
- All user workflow tests passing
- All invite workflow tests passing
- Tests use authentication mocks via `authenticated_client` helper

⏸️ **Playwright Tests: 29 failed** (timeouts - frontend not running)
- Tests timeout waiting for frontend elements
- Need frontend running to pass

## Running Tests

### Quick Test (API only - recommended for development):
```bash
TEST_MODE=true uv run pytest tests/e2e/ -k "not playwright" -v --no-cov
```

### All E2E Tests (requires frontend):
```bash
# Terminal 1: Start frontend
cd frontend && npm run dev

# Terminal 2: Run tests
TEST_MODE=true uv run pytest tests/e2e/ -v --no-cov
```

## Test Helpers

### `authenticated_client` Context Manager
Use this helper to mock authentication in tests:

```python
from test_user_workflows import authenticated_client

def test_something(test_client):
    with authenticated_client(test_client, user_role="team-fan"):
        response = test_client.get("/api/matches")
        assert response.status_code == 200
```

