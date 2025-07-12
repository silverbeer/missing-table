# Test Suite Documentation

This directory contains comprehensive tests for the sports league management backend.

## Test Structure

### Test Files
- `test_supabase_connection.py` - Tests direct Supabase connection and basic database operations
- `test_dao.py` - Tests the Enhanced DAO layer functionality
- `test_api_endpoints.py` - Tests all FastAPI endpoints
- `test_cli.py` - Tests CLI functionality
- `test_e2e_supabase.py` - Legacy comprehensive e2e test (kept for reference)

### Configuration Files
- `conftest.py` - Pytest fixtures and configuration
- `pytest.ini` - Pytest settings and markers
- `.coveragerc` - Coverage configuration
- `README.md` - This documentation

## Prerequisites

### 1. Local Supabase Setup
Make sure you have a local Supabase instance running:

```bash
# Start local Supabase (from backend directory)
./scripts/start/start_local.sh

# Or manually start Supabase CLI
supabase start
```

### 2. Environment Variables
Create a `.env.local` file in the backend directory:

```bash
# Local Supabase Configuration
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=your_service_key_here
SUPABASE_ANON_KEY=your_anon_key_here
```

**Note**: Get your keys by running `supabase status` after starting the local instance.

### 3. Database Setup
Ensure your database has reference data:

```bash
# Run database setup scripts
uv run python scripts/setup/populate_reference_data.py
```

## Running Tests

### Run All Tests
```bash
# From backend directory
uv run pytest
```

### Run by Category
```bash
# Integration tests (database connection)
uv run pytest -m integration

# End-to-end tests (full API)
uv run pytest -m e2e

# Slow tests (CLI)
uv run pytest -m slow

# Fast tests only
uv run pytest -m "not slow"
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

#### "Local Supabase not running"
```bash
# Start local Supabase
supabase start

# Check status
supabase status
```

#### "SUPABASE_SERVICE_KEY not set"
```bash
# Get your keys
supabase status

# Set environment variables
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_KEY=your_key_here
```

#### "Reference data missing"
```bash
# Populate reference data
uv run python scripts/setup/populate_reference_data.py
```

#### API tests failing
```bash
# Make sure FastAPI server is NOT running during tests
# Tests use TestClient which starts its own server
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