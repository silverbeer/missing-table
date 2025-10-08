# API Contract Testing Infrastructure

## 🎯 Overview

This project implements a comprehensive API contract testing infrastructure that ensures:

✅ **100% API coverage visibility** - Know exactly which endpoints are tested
✅ **Type-safe API client** - Catch breaking changes at compile time
✅ **Automated test generation** - Property-based testing finds edge cases
✅ **CI/CD integration** - Automated coverage checks on every PR
✅ **Living documentation** - API client serves as usage examples

## 📁 Architecture

```
backend/
├── api_client/              # Type-safe API client
│   ├── __init__.py
│   ├── client.py           # Main client with all endpoint methods
│   ├── models.py           # Auto-generated Pydantic models from OpenAPI
│   └── exceptions.py       # Custom exception hierarchy
│
├── tests/contract/          # Contract test suite
│   ├── conftest.py         # Test fixtures (authenticated clients, etc.)
│   ├── test_schemathesis.py    # Property-based tests
│   ├── test_auth_contract.py   # Authentication contract tests
│   ├── test_games_contract.py  # Games endpoint contract tests
│   └── README.md           # Detailed testing documentation
│
├── scripts/
│   ├── export_openapi.py       # Export clean OpenAPI schema
│   ├── generate_api_models.py  # Generate Pydantic models from schema
│   ├── check_api_coverage.py   # Coverage gap analyzer
│   └── install_hooks.sh        # Install git hooks
│
└── openapi.json            # OpenAPI 3.1 schema (auto-generated)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd backend
uv sync  # Installs all dev dependencies including schemathesis
```

### 2. Run Contract Tests

```bash
# Run all contract tests
uv run pytest tests/contract/ -m contract -v

# Run specific test suite
uv run pytest tests/contract/test_auth_contract.py -v

# Run property-based tests only
uv run pytest tests/contract/test_schemathesis.py -v
```

### 3. Check API Coverage

```bash
# Generate coverage report
uv run python scripts/check_api_coverage.py

# With specific threshold
uv run python scripts/check_api_coverage.py --threshold 85 --fail-below

# JSON output for CI/CD
uv run python scripts/check_api_coverage.py --format json
```

### 4. Install Git Hooks (Optional)

```bash
./scripts/install_hooks.sh
```

This installs a pre-commit hook that:
- Exports latest OpenAPI schema
- Checks API test coverage
- Warns if coverage is below threshold

## 🏗️ Components

### 1. Type-Safe API Client

**Location:** `api_client/`

Fully typed Python client with:
- Pydantic models for request/response validation
- Automatic JWT token management
- Built-in error handling with custom exceptions
- Type hints for IDE autocomplete

**Example Usage:**

```python
from api_client import MissingTableClient, GamePatch

# Create client and login
with MissingTableClient(base_url="http://localhost:8000") as client:
    client.login(email="user@example.com", password="password")

    # Get games with filters
    games = client.get_games(season_id=1, age_group_id=2, limit=10)

    # Update game score (PATCH endpoint)
    patch = GamePatch(home_score=3, away_score=2, status="played")
    client.patch_game(game_id=5, game_patch=patch)

    # Get league standings
    standings = client.get_table(season_id=1, age_group_id=2)
```

### 2. Property-Based Testing (Schemathesis)

**Location:** `tests/contract/test_schemathesis.py`

Schemathesis automatically:
- Reads OpenAPI schema
- Generates hundreds of test cases with random valid data
- Tests ALL endpoints (even ones you forgot about)
- Validates responses against schema
- Finds edge cases (null values, boundary conditions, etc.)

**Benefits:**
- Catches schema violations
- Finds 500 errors on edge inputs
- Tests error paths
- No manual test writing needed

### 3. Manual Contract Tests

**Location:** `tests/contract/test_*.py`

Explicit tests for:
- Authentication flows (login, signup, logout, refresh)
- Authorization (role-based access control)
- Business logic (game status updates, score validation)
- Error handling (404, 401, 422, etc.)

**Why both?**
- Schemathesis: Broad coverage, finds unexpected issues
- Manual tests: Specific business requirements, critical paths

### 4. Coverage Gap Analyzer

**Location:** `scripts/check_api_coverage.py`

Automated tool that:
1. Parses OpenAPI schema to extract all endpoints
2. Scans test files to find tested endpoints
3. Compares and identifies gaps
4. Generates rich reports

**Output Example:**

```
Overall Coverage:
  Endpoints: 28/37 (75.7%)
  Methods: 35/49 (71.4%)

Coverage by Category:
  ✅ auth: 9/9 (100%)
  ⚠️  games: 4/6 (67%)
  ❌ security: 0/4 (0%)

Endpoint Coverage Details:
Path                    Methods         Tested      Untested    Status
/api/games/{game_id}    PUT,PATCH,DEL  PUT,PATCH   DELETE      ⚠️
/api/security/analytics GET            -           GET         ❌
```

## 📊 CI/CD Integration

### GitHub Actions

**Workflow:** `.github/workflows/api-contract-tests.yml`

Runs on every push/PR:
1. Exports fresh OpenAPI schema
2. Validates schema
3. Runs all contract tests
4. Runs Schemathesis property tests
5. Checks coverage against threshold
6. Comments on PR with coverage report

### Pre-commit Hook

Install with: `./scripts/install_hooks.sh`

Runs before each commit:
- Exports OpenAPI schema
- Checks coverage
- Warns if below threshold
- Allows override with `git commit --no-verify`

## 🔄 Workflow

### Adding a New Endpoint

1. **Implement endpoint** in `app.py`

2. **Add to API client** (if complex):
   ```bash
   # Regenerate models from updated schema
   uv run python scripts/export_openapi.py
   uv run python scripts/generate_api_models.py

   # Add method to api_client/client.py (if needed)
   ```

3. **Write contract test**:
   ```python
   # tests/contract/test_my_feature_contract.py
   @pytest.mark.contract
   def test_my_new_endpoint(api_client: MissingTableClient):
       response = api_client.my_new_method(param=value)
       assert response["field"] == expected_value
   ```

4. **Verify coverage**:
   ```bash
   uv run pytest tests/contract/test_my_feature_contract.py -v
   uv run python scripts/check_api_coverage.py
   ```

### Debugging Coverage Gaps

If coverage shows 0% for a tested endpoint:

**Problem:** Pattern matching in coverage analyzer doesn't detect your test

**Solution:** Use standard patterns:

```python
# ✅ Will be detected
response = client.get("/api/games")
api_client.post("/api/teams", json=data)
authenticated_client._request("PATCH", "/api/games/1", json_data=patch)

# ❌ May not be detected
endpoint = build_url("games")  # Dynamic construction
response = client.get(endpoint)
```

## 🎓 Best Practices

### Writing Contract Tests

1. **Test the contract, not implementation**
   ```python
   # ✅ Good - tests API contract
   def test_login_returns_tokens(api_client):
       response = api_client.login(email, password)
       assert "access_token" in response
       assert "refresh_token" in response

   # ❌ Bad - tests implementation details
   def test_login_creates_session_in_redis(api_client):
       ...  # Don't test internals
   ```

2. **Use fixtures for auth**
   ```python
   @pytest.fixture
   def authenticated_client():
       client = MissingTableClient()
       client.login(...)
       yield client
       client.close()
   ```

3. **Test error cases**
   ```python
   def test_auth_errors(api_client):
       with pytest.raises(AuthenticationError):
           api_client.login(email="bad", password="wrong")
   ```

4. **Keep tests independent**
   - No shared state between tests
   - Use transaction rollback if mutating data
   - Clean up created resources

### Maintaining High Coverage

1. **Monitor coverage in CI/CD**
   - Set threshold in workflow (currently 70%)
   - Gradually increase threshold
   - Block merges below threshold

2. **Review coverage before commits**
   - Pre-commit hook warns you
   - Run manually: `uv run python scripts/check_api_coverage.py`

3. **Prioritize critical paths**
   - Auth endpoints: 100%
   - Data mutation (POST/PUT/PATCH): High priority
   - Read-only (GET): Lower priority

## 🔧 Troubleshooting

### Schemathesis Tests Failing

**Error:** `Schema validation failed`

**Solution:**
```bash
# Validate OpenAPI schema
uv run python -c "from openapi_spec_validator import validate; import json; validate(json.load(open('openapi.json')))"

# Regenerate clean schema
uv run python scripts/export_openapi.py
```

### Model Generation Fails

**Error:** `yaml.scanner.ScannerError`

**Cause:** Log output mixed with JSON in openapi.json

**Solution:**
```bash
# Use export_openapi.py instead of manual export
uv run python scripts/export_openapi.py
```

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'api_client'`

**Solution:**
```bash
# Ensure you're in backend directory
cd backend

# Install in development mode
uv sync

# Run tests from backend directory
uv run pytest tests/contract/
```

## 📈 Metrics & Goals

### Current Coverage
Run: `uv run python scripts/check_api_coverage.py`

### Coverage Goals
- **Phase 1:** 70% method coverage ✅
- **Phase 2:** 85% method coverage
- **Phase 3:** 95% method coverage
- **Phase 4:** 100% critical path coverage

### Testing Pyramid
```
      /\        E2E Tests (10%)
     /  \       Integration Tests (20%)
    /    \      Contract Tests (30%)
   /      \     Unit Tests (40%)
  /________\
```

## 📚 Additional Resources

- [Schemathesis Documentation](https://schemathesis.io/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)

## 🤝 Contributing

When adding new endpoints:
1. Update OpenAPI schema (FastAPI does this automatically)
2. Regenerate models: `uv run python scripts/generate_api_models.py`
3. Add contract tests in `tests/contract/`
4. Verify coverage: `uv run python scripts/check_api_coverage.py`
5. Ensure CI passes before merging

---

**Questions?** See `tests/contract/README.md` for more detailed examples.
