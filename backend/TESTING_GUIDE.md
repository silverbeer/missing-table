# Testing Guide

## Test Organization

The backend has multiple test types organized by purpose and requirements:

```
tests/
├── contract/                      # API contract tests (REQUIRES RUNNING SERVER)
│   ├── test_auth_contract.py     # Authentication contract tests
│   ├── test_games_contract.py    # Games endpoint contract tests
│   └── test_schemathesis.py      # Property-based schema tests (future)
│
├── test_api_endpoints.py          # E2E API tests (REQUIRES RUNNING SERVER)
├── test_auth_endpoints.py         # E2E auth tests (REQUIRES RUNNING SERVER)
├── test_enhanced_e2e.py           # Enhanced E2E tests (REQUIRES RUNNING SERVER)
├── test_invite_e2e.py             # Invite flow E2E tests (REQUIRES RUNNING SERVER)
│
├── test_dao.py                    # DAO unit tests (NO SERVER NEEDED)
├── test_supabase_connection.py   # Connection tests (NO SERVER NEEDED)
└── test_cli.py                    # CLI tests (NO SERVER NEEDED)
```

## Test Categories

### 1. Unit Tests (Fast, No Server Required)
**Markers:** `@pytest.mark.unit`
**Run:** `uv run pytest -m unit -v`

Tests isolated functions and classes without external dependencies.

**Examples:**
- `test_dao.py` - Data access layer unit tests
- `test_supabase_connection.py` - Connection logic tests

**Characteristics:**
- ✅ Fast (<100ms per test)
- ✅ No network calls
- ✅ No database needed
- ✅ Run in CI/CD always

### 2. Integration Tests (Medium Speed, Database Required)
**Markers:** `@pytest.mark.integration`
**Run:** `uv run pytest -m integration -v`

Tests interaction between components with real database.

**Requirements:**
- Supabase instance running (local or cloud)
- Database schema migrated
- Environment variables configured

**Characteristics:**
- ⏱️  Medium speed (100ms-1s per test)
- 🗄️  Real database calls
- 🔧 Setup/teardown needed

### 3. E2E Tests (Slow, Full Stack Required)
**Markers:** `@pytest.mark.e2e`
**Run:** `uv run pytest -m e2e -v`

Tests full API workflows through HTTP endpoints.

**Requirements:**
- ✅ **Backend server running** (`uv run python app.py`)
- ✅ Database available
- ✅ All services initialized

**Examples:**
- `test_api_endpoints.py` - Tests GET/POST/PUT/DELETE endpoints
- `test_auth_endpoints.py` - Tests login/signup/logout flows
- `test_enhanced_e2e.py` - Tests complex workflows

**Characteristics:**
- 🐌 Slow (1-5s per test)
- 🌐 Real HTTP requests
- 🔐 Full authentication stack
- 💾 Database state changes

### 4. Contract Tests (Slow, Full Stack Required)
**Markers:** `@pytest.mark.contract`
**Run:** `uv run pytest -m contract -v`

Tests API behavior against OpenAPI schema specification.

**Requirements:**
- ✅ **Backend server running** (http://localhost:8000)
- ✅ OpenAPI schema up-to-date
- ✅ All endpoints available

**Purpose:**
- Validates API contract compliance
- Ensures requests/responses match schema
- Type-safe client testing
- Business logic validation

**Characteristics:**
- 🐌 Slow (1-5s per test)
- 📋 Schema-driven
- 🔒 Type-safe
- 📊 Coverage tracked

## Quick Reference

### Run All Tests (Requires Server)
```bash
# Start server first
uv run python app.py &
SERVER_PID=$!

# Wait for server to be ready
sleep 3

# Run all tests
uv run pytest -v

# Cleanup
kill $SERVER_PID
```

### Run Only Fast Tests (No Server)
```bash
uv run pytest -m "unit or integration" -v
```

### Run Contract Tests (Requires Server)
```bash
# 1. Start server
./missing-table.sh start

# 2. Run contract tests
uv run pytest tests/contract/ -m contract -v

# 3. Stop server
./missing-table.sh stop
```

### Run E2E Tests (Requires Server)
```bash
# Start server
./missing-table.sh dev

# Run E2E tests
uv run pytest -m e2e -v
```

## Server Check Helper

Contract and E2E tests automatically check if the server is running. If not, they will:
1. Print clear error message
2. Show how to start the server
3. Skip tests gracefully

Example output when server not running:
```
❌ Backend server is not running at http://localhost:8000

   Please start the server first:

   Terminal 1:
   $ ./missing-table.sh dev

   Terminal 2:
   $ uv run pytest tests/contract/ -m contract -v
```

## Best Practices

### Local Development
1. **Run unit tests frequently** - They're fast
   ```bash
   uv run pytest -m unit -v --tb=short
   ```

2. **Run integration tests before commit** - Catch database issues
   ```bash
   uv run pytest -m integration -v
   ```

3. **Run contract tests for API changes** - Validate contract
   ```bash
   ./missing-table.sh dev  # Terminal 1
   uv run pytest tests/contract/ -m contract -v  # Terminal 2
   ```

### CI/CD
Tests run in this order:
1. ✅ Unit tests (always)
2. ✅ Integration tests (if database available)
3. ✅ Contract tests (server started automatically)
4. ✅ E2E tests (server started automatically)

See `.github/workflows/api-contract-tests.yml` for CI configuration.

## Troubleshooting

### "Connection refused" errors
**Problem:** Server not running
**Solution:**
```bash
# Check if server is running
curl http://localhost:8000/health

# If not, start it
./missing-table.sh dev
```

### "Database connection failed"
**Problem:** Supabase not available
**Solution:**
```bash
# Local Supabase
npx supabase start

# Or switch to prod environment
./switch-env.sh prod
```

### "Test collection errors"
**Problem:** Import errors or missing dependencies
**Solution:**
```bash
# Reinstall dependencies
uv sync

# Check imports
uv run python -c "import api_client; print('OK')"
```

### Contract tests show 0% coverage
**Problem:** Tests not using standard patterns
**Solution:** See `scripts/check_api_coverage.py` documentation

## Writing New Tests

### Unit Test Example
```python
import pytest

@pytest.mark.unit
def test_my_function():
    """Unit test - no external dependencies."""
    result = my_function(input_data)
    assert result == expected
```

### Integration Test Example
```python
import pytest

@pytest.mark.integration
def test_database_query(supabase_client):
    """Integration test - uses real database."""
    result = supabase_client.table('teams').select('*').execute()
    assert len(result.data) > 0
```

### E2E Test Example
```python
import pytest

@pytest.mark.e2e
def test_api_workflow(test_client):
    """E2E test - uses TestClient (no server needed for this)."""
    response = test_client.get('/api/teams')
    assert response.status_code == 200
```

### Contract Test Example
```python
import pytest
from api_client import MissingTableClient

@pytest.mark.contract
def test_games_endpoint_contract(api_client: MissingTableClient):
    """Contract test - validates against OpenAPI schema."""
    games = api_client.get_games(limit=10)
    assert isinstance(games, list)
    # Response structure validated by Pydantic models
```

## Coverage

### Code Coverage
```bash
# Run with coverage
uv run pytest --cov=. --cov-report=html

# View report
open htmlcov/index.html
```

### API Contract Coverage
```bash
# Check which endpoints are tested
uv run python scripts/check_api_coverage.py

# With threshold
uv run python scripts/check_api_coverage.py --threshold 85 --fail-below
```

## Summary Table

| Test Type | Marker | Server Required? | Database Required? | Speed | Run Frequency |
|-----------|--------|------------------|-------------------|-------|---------------|
| Unit | `unit` | ❌ No | ❌ No | ⚡ Fast | Every save |
| Integration | `integration` | ❌ No | ✅ Yes | ⏱️ Medium | Before commit |
| E2E | `e2e` | ✅ Yes | ✅ Yes | 🐌 Slow | Before PR |
| Contract | `contract` | ✅ Yes | ✅ Yes | 🐌 Slow | API changes |

---

**Questions?** See `API_CONTRACT_TESTING.md` for contract testing details.
