# API Contract Testing

Comprehensive contract testing infrastructure for the Missing Table API.

## Overview

This package provides:

1. **Type-Safe API Client** - Fully typed client with Pydantic models
2. **Property-Based Testing** - Schemathesis for automated test generation
3. **Manual Contract Tests** - Explicit tests for critical business logic
4. **Coverage Gap Analysis** - Automated detection of untested endpoints

## Quick Start

### Run All Contract Tests

```bash
# Run all contract tests
uv run pytest tests/contract/ -m contract

# Run with verbose output
uv run pytest tests/contract/ -m contract -v

# Run specific test file
uv run pytest tests/contract/test_auth_contract.py -v
```

### Check API Coverage

```bash
# Generate coverage report
uv run python scripts/check_api_coverage.py

# JSON output
uv run python scripts/check_api_coverage.py --format json

# Fail if below threshold
uv run python scripts/check_api_coverage.py --threshold 85 --fail-below
```

### Regenerate API Models

When the OpenAPI schema changes, regenerate the models:

```bash
uv run python scripts/export_openapi.py  # Export fresh schema
uv run python scripts/generate_api_models.py  # Generate models
```

## Architecture

### API Client (`api_client/`)

Type-safe client with:
- Full Pydantic model validation
- Automatic JWT token management
- Built-in error handling
- Request/response logging

Example usage:

```python
from api_client import MissingTableClient

with MissingTableClient(base_url="http://localhost:8000") as client:
    # Login
    client.login(email="user@example.com", password="password")

    # Get games
    games = client.get_games(season_id=1, limit=10)

    # Patch a game score
    from api_client.models import GamePatch
    patch = GamePatch(home_score=3, away_score=2, status="played")
    client.patch_game(game_id=5, game_patch=patch)
```

### Property-Based Tests (`test_schemathesis.py`)

Schemathesis automatically:
- Generates test cases from OpenAPI schema
- Tests all endpoints with random valid data
- Validates responses against schema
- Detects edge cases and schema violations

### Manual Contract Tests

- `test_auth_contract.py` - Authentication & authorization
- `test_games_contract.py` - Games CRUD & business logic
- More test files can be added following this pattern

### Coverage Analyzer (`scripts/check_api_coverage.py`)

Parses:
1. OpenAPI schema to extract all endpoints
2. Test files to find tested endpoints
3. Compares and reports gaps

Output includes:
- Overall coverage percentage
- Coverage by category (auth, games, teams, etc.)
- Detailed endpoint-by-endpoint report
- Identification of untested endpoints

## Test Categories

### Contract Tests (`@pytest.mark.contract`)

API contract verification:
- Request/response structure
- Status codes
- Error handling
- Data validation

### Property-Based Tests

Automated fuzzing:
- Random valid inputs
- Edge case discovery
- Schema compliance
- Error boundary testing

## CI/CD Integration

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: api-coverage
      name: Check API test coverage
      entry: uv run python backend/scripts/check_api_coverage.py --threshold 80 --fail-below
      language: system
      pass_filenames: false
      always_run: true
```

### GitHub Actions

Add to `.github/workflows/api-tests.yml`:

```yaml
name: API Contract Tests

on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          cd backend
          pip install uv
          uv sync

      - name: Run contract tests
        run: |
          cd backend
          uv run pytest tests/contract/ -m contract -v

      - name: Check API coverage
        run: |
          cd backend
          uv run python scripts/check_api_coverage.py --threshold 85 --fail-below
```

## Best Practices

### Writing Contract Tests

1. **Test the contract, not the implementation**
   - Verify request/response structure
   - Don't test internal logic

2. **Use the API client**
   - Provides type safety
   - Catches breaking changes

3. **Test error cases**
   - 4xx errors (client errors)
   - 5xx errors (server errors)
   - Validation failures

4. **Keep tests independent**
   - No shared state
   - Use fixtures for setup/teardown

### Maintaining Coverage

1. **Add tests for new endpoints**
   - Create contract test when adding endpoint
   - Update API client if needed

2. **Monitor coverage reports**
   - Run before commits
   - Check in CI/CD

3. **Regenerate models regularly**
   - After schema changes
   - Before major releases

## Troubleshooting

### Coverage shows 0% for existing tests

The coverage analyzer uses pattern matching to find API calls. Ensure your tests use standard patterns:

```python
# ✅ Good - will be detected
response = client.get("/api/games")
api_client.post("/api/teams", json=data)
self._request("PATCH", "/api/games/1", json_data=patch)

# ❌ Bad - may not be detected
endpoint = "/api/games"
response = client.get(endpoint)  # Dynamic endpoints may not be detected
```

### Schemathesis tests failing

1. Check OpenAPI schema is valid:
   ```bash
   uv run python -c "from openapi_spec_validator import validate; import json; validate(json.load(open('openapi.json')))"
   ```

2. Ensure test database has reference data

3. Check authentication setup in conftest.py

### Model generation fails

1. Ensure OpenAPI schema is clean (no log output):
   ```bash
   uv run python scripts/export_openapi.py
   ```

2. Check for schema validation errors

3. Try with `--debug` flag for more info

## Next Steps

1. **Increase coverage** - Add tests for untested endpoints
2. **Add integration tests** - Test multi-step workflows
3. **Performance testing** - Add benchmarks for critical paths
4. **Generate SDK** - Create TypeScript client for frontend
