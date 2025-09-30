# Test Suite Documentation

This directory contains comprehensive tests for the sports league management backend.

## Test Structure

### Test Files
- **`test_api_endpoints.py`** - Basic API endpoint functionality tests (**NEW - 76 e2e tests**)
- **`test_auth_endpoints.py`** - Authentication and authorization tests (**NEW - Comprehensive auth testing**)
- **`test_enhanced_e2e.py`** - Complex workflows and business logic tests (**NEW - Advanced e2e scenarios**)
- `test_dao.py` - Tests the Enhanced DAO layer functionality
- `test_supabase_connection.py` - Tests direct Supabase connection and basic database operations (if exists)
- `test_cli.py` - Tests CLI functionality (if exists)
- Legacy files kept for reference

### New E2E Test Coverage
## 🚀 Quick Start

**Want to run comprehensive e2e tests right now?**

```bash
# 1. Setup isolated test database (one-time)
./scripts/e2e-db-setup.sh

# 2. Seed with test data (one-time)  
./scripts/e2e-db-seed.sh

# 3. Run all 76 e2e tests
cd backend && uv run pytest -m e2e
```

✅ **Safe**: Uses separate database - won't affect your development data  
✅ **Fast**: Clean test data provides consistent, quick test runs  
✅ **Comprehensive**: Tests all API endpoints, auth flows, and business logic

## Test Coverage Summary

The new test suite provides **76 comprehensive e2e tests** covering:

#### Core API Endpoints (test_api_endpoints.py)
- **Health checks** - Basic `/health` and comprehensive `/health/full`
- **Reference data** - Age groups, seasons, game types, divisions, positions
- **Teams** - Team listing, filtering, validation
- **Games** - Game data, filtering, team-specific games  
- **League tables** - Standings calculation and filtering
- **Error handling** - Invalid inputs, edge cases, malformed requests

#### Authentication & Security (test_auth_endpoints.py)
- **Signup flows** - Valid/invalid email, password strength, missing fields
- **Login flows** - Credential validation, rate limiting
- **Token management** - Refresh tokens, JWT validation, token formats
- **Protected endpoints** - Authorization requirements testing
- **Admin endpoints** - Role-based access control validation
- **Security edge cases** - Malformed tokens, rate limiting, input validation

#### Advanced Workflows (test_enhanced_e2e.py)
- **Invite system** - Complete invite workflow testing (8 endpoints)
- **Game lifecycle** - Data consistency across multiple endpoints
- **Business logic** - Standings calculations, referential integrity
- **Filtering & pagination** - Complex filter combinations, limits
- **Data integrity** - Cross-endpoint validation, concurrent access
- **Edge cases** - Extreme values, invalid parameters, system stability

### Configuration Files
- `conftest.py` - Pytest fixtures and configuration
- `pytest.ini` - Pytest settings and markers
- `.coveragerc` - Coverage configuration
- `README.md` - This documentation

## Prerequisites

### Database Setup Options

The test suite uses a **separate e2e database** that's isolated from your development data.

#### Option 1: E2E Tests (Recommended)
For running the new comprehensive e2e test suite:

```bash
# 1. Setup E2E test database (isolated from development)
./scripts/e2e-db-setup.sh

# 2. Seed with minimal test data
./scripts/e2e-db-seed.sh

# 3. Run e2e tests
cd backend && uv run pytest -m e2e
```

#### Option 2: Legacy Integration Tests
For running legacy integration tests against local development database:

```bash
# 1. Start local development database
supabase start --workdir supabase-local

# 2. Restore production-like data
./scripts/db_tools.sh restore

# 3. Run integration tests
cd backend && uv run pytest -m integration
```

### Environment Files
The test suite automatically uses the appropriate environment:
- **E2E tests**: Uses `.env.e2e` (automatically loaded)
- **Integration tests**: Uses `.env.local` (for development database)

### Database Isolation
- **Local Development**: `supabase-local/` (port 54321) - Your development data
- **E2E Testing**: `supabase-e2e/` (separate instance) - Clean test data
- Tests are prevented from accidentally using development database

## Running Tests

### Quick Start - E2E Tests
```bash
# Setup and run e2e tests (recommended)
./scripts/e2e-db-setup.sh && ./scripts/e2e-db-seed.sh
cd backend && uv run pytest -m e2e
```

### Run All Tests
```bash
# From backend directory
uv run pytest
```

### Run by Category
```bash
# E2E tests (recommended - comprehensive API testing)
uv run pytest -m e2e

# Integration tests (database connection)
uv run pytest -m integration

# Slow tests (CLI)
uv run pytest -m slow

# Fast tests only
uv run pytest -m "not slow"
```

### E2E Test Categories
```bash
# Basic API endpoint tests
uv run pytest tests/test_api_endpoints.py

# Authentication and security tests
uv run pytest tests/test_auth_endpoints.py

# Complex workflow tests
uv run pytest tests/test_enhanced_e2e.py

# All e2e tests with coverage
uv run pytest -m e2e --cov=.
```

### Run Specific Test Files
```bash
# Test Supabase connection
uv run pytest tests/test_supabase_connection.py

# Test DAO layer
uv run pytest tests/test_dao.py

# Test API endpoints
uv run pytest tests/test_api_endpoints.py

# Test CLI
uv run pytest tests/test_cli.py
```

## Code Coverage

### Basic Coverage
```bash
# Run tests with coverage
uv run pytest --cov=.

# Run tests with coverage report
uv run pytest --cov=. --cov-report=term-missing
```

### HTML Coverage Reports
```bash
# Generate HTML coverage report
uv run pytest --cov=. --cov-report=html

# View the report
open htmlcov/index.html
```

### XML Coverage Reports (for CI)
```bash
# Generate XML coverage report
uv run pytest --cov=. --cov-report=xml

# Creates coverage.xml file
```

### Coverage by Category
```bash
# Coverage for integration tests only
uv run pytest -m integration --cov=. --cov-report=html

# Coverage for e2e tests only
uv run pytest -m e2e --cov=. --cov-report=html

# Coverage excluding slow tests
uv run pytest -m "not slow" --cov=. --cov-report=html
```

### Coverage Configuration
Coverage is configured in `.coveragerc`:
- **Source**: Current directory (.)
- **Omits**: Test files, cache, virtual environments, scripts
- **Excludes**: Abstract methods, main blocks, type checking
- **Reports**: HTML in `htmlcov/`, XML in `coverage.xml`

### Coverage Targets
Aim for these coverage targets:
- **Overall**: 80%+ (excluding scripts and utilities)
- **Core modules**: 90%+ (app.py, dao/)
- **API endpoints**: 95%+ (all endpoints tested)
- **Business logic**: 85%+ (DAO methods, calculations)

### Coverage Examples
```bash
# Quick coverage check
uv run pytest --cov=. --cov-report=term --cov-fail-under=80

# Detailed coverage with missing lines
uv run pytest --cov=. --cov-report=term-missing --cov-branch

# Coverage for specific modules
uv run pytest --cov=dao --cov-report=html tests/test_dao.py

# Coverage excluding external dependencies
uv run pytest --cov=. --cov-report=html --cov-config=.coveragerc
```

## Test Markers

### `@pytest.mark.integration`
Tests that require database connection but don't test the full API stack.

### `@pytest.mark.e2e`
End-to-end tests that test the complete API functionality.

### `@pytest.mark.slow`
Slow running tests (typically CLI tests with subprocess calls).

## Test Data

### Fixtures
The test suite uses pytest fixtures for:
- `test_client` - FastAPI test client
- `supabase_client` - Direct Supabase client
- `enhanced_dao` - DAO instance
- `sample_team_data` - Sample team data
- `sample_game_data` - Sample game data

### Test Database
Tests run against your local Supabase instance. The tests are designed to:
- Work with existing data
- Not modify data unless specifically testing CRUD operations
- Handle empty tables gracefully

## Troubleshooting

### Common Issues

#### "E2E Supabase not running" 
```bash
# Setup E2E database
./scripts/e2e-db-setup.sh

# Check status
./scripts/e2e-db-setup.sh --status

# Stop E2E database
./scripts/e2e-db-setup.sh --stop
```

#### "Tests must run against e2e database"
This error means tests are trying to use the development database. Fix:
```bash
# Ensure E2E database is running
./scripts/e2e-db-setup.sh

# Check that .env.e2e exists and has correct port (55321)
cat .env.e2e

# Tests should automatically load .env.e2e
```

#### "Reference data missing" in E2E tests
```bash
# Seed E2E database with test data
./scripts/e2e-db-seed.sh

# Reset E2E database if corrupted
./scripts/e2e-db-seed.sh --reset
```

#### Running both databases simultaneously
```bash
# Development database (port 54321)
supabase start --workdir supabase-local

# E2E database (separate instance) 
./scripts/e2e-db-setup.sh

# Both can run at the same time on different ports
```

#### Legacy: "Local Supabase not running"
```bash
# For integration tests against development database
supabase start --workdir supabase-local
supabase status
```

#### API tests failing
```bash
# Make sure FastAPI server is NOT running during tests
# Tests use TestClient which starts its own server

# Ensure using correct database
uv run pytest -m e2e -v  # Should show e2e database URL in output
```

#### Coverage issues
```bash
# Clean coverage data
rm -rf .coverage htmlcov/

# Re-run with fresh coverage
uv run pytest --cov=. --cov-report=html
```

### Debug Mode
```bash
# Run tests with verbose output
uv run pytest -v -s

# Run single test with debug
uv run pytest tests/test_supabase_connection.py::test_supabase_connection -v -s

# Run with coverage debug
uv run pytest --cov=. --cov-report=term-missing -v
```

## Continuous Integration

The test suite is designed for CI/CD:
- Uses markers to run different test categories
- Handles missing dependencies gracefully
- Includes timeout and error handling
- Provides clear failure messages
- Generates coverage reports for CI

### Example CI Commands
```bash
# Quick smoke test
uv run pytest -m "not slow" --tb=short

# Full test suite with coverage
uv run pytest --cov=. --cov-report=xml --tb=short

# Integration tests only
uv run pytest -m integration --cov=. --cov-report=term

# Fail if coverage below threshold
uv run pytest --cov=. --cov-fail-under=80
```

### CI Coverage Integration
```yaml
# Example GitHub Actions step
- name: Run tests with coverage
  run: |
    uv run pytest --cov=. --cov-report=xml
    
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Adding New Tests

### Follow the Pattern
1. Use appropriate markers (`@pytest.mark.integration`, `@pytest.mark.e2e`, etc.)
2. Use fixtures from `conftest.py`
3. Handle cases where data may be empty
4. Add clear docstrings
5. Include error handling tests
6. Aim for high coverage of new code

### Example Test
```python
@pytest.mark.integration
def test_new_functionality(enhanced_dao):
    \"\"\"Test new DAO functionality.\"\"\"
    result = enhanced_dao.new_method()
    assert result is not None
    assert isinstance(result, list)
```

## Performance

The test suite is optimized for speed:
- Uses session-scoped fixtures
- Minimizes database calls
- Uses TestClient for API tests (faster than real HTTP)
- Marks slow tests appropriately

Typical run times:
- Integration tests: ~10-20 seconds
- E2E tests: ~30-45 seconds
- CLI tests: ~60-90 seconds
- Full suite: ~2-3 minutes
- Coverage generation: +10-20 seconds

## Coverage Reports

### HTML Report Features
- **File-by-file coverage**: See coverage for each Python file
- **Line-by-line highlighting**: Red lines are not covered
- **Branch coverage**: Shows which branches are tested
- **Summary statistics**: Overall coverage percentages
- **Missing lines**: Exact lines that need tests

### Reading Coverage Reports
- **Green lines**: Covered by tests
- **Red lines**: Not covered by tests
- **Yellow lines**: Partially covered (branches)
- **Coverage %**: Percentage of lines covered
- **Missing**: Line numbers not covered

### Improving Coverage
1. **Identify gaps**: Look for red lines in HTML report
2. **Add tests**: Write tests for uncovered code
3. **Test edge cases**: Cover error conditions
4. **Test branches**: Cover all if/else paths
5. **Mock external deps**: Test without external services 