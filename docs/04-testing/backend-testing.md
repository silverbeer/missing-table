# Backend Testing Guide

## Overview

This document provides comprehensive information about testing the sports league management backend. The testing suite includes unit tests, integration tests, end-to-end tests, and CLI tests.

## Test Structure

### Test Categories

The tests are organized into several categories using pytest markers:

- **`@pytest.mark.unit`** - Fast, isolated unit tests
- **`@pytest.mark.integration`** - Tests requiring database connection
- **`@pytest.mark.e2e`** - End-to-end tests covering complete workflows
- **`@pytest.mark.slow`** - Slow-running tests (primarily CLI tests)

### Test Files

```
tests/
├── conftest.py                 # Pytest configuration and fixtures
├── test_api_endpoints.py       # Comprehensive API endpoint tests
├── test_auth_endpoints.py      # Authentication and authorization tests
├── test_supabase_connection.py # Database connection and integration tests
├── test_dao.py                 # Data Access Object (DAO) tests
├── test_cli.py                 # Command Line Interface tests
├── test_enhanced_e2e.py        # Advanced end-to-end workflow tests
└── README.md                   # Test documentation
```

## Prerequisites

### 1. Environment Setup

Ensure you have the required dependencies:

```bash
# Install development dependencies
uv sync --dev

# Or manually install test dependencies
uv add --dev pytest pytest-cov pytest-asyncio coverage
```

### 2. Database Setup

For integration and e2e tests, you need a local Supabase instance:

```bash
# Start local Supabase
cd backend
supabase start

# Get connection details
supabase status
```

### 3. Environment Variables

Create a `.env.local` file in the backend directory:

```bash
# Local Supabase Configuration (get from `supabase status`)
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=your_service_key_here
SUPABASE_ANON_KEY=your_anon_key_here

# Optional: Disable security features for testing
DISABLE_SECURITY=true
```

### 4. Test Data

Ensure your database has reference data:

```bash
# Populate reference data
uv run python scripts/setup/populate_reference_data.py
```

## Running Tests

### Quick Start

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Use the custom test runner
uv run python run_tests.py --coverage --html-coverage
```

### Test Categories

```bash
# Run only unit tests (fast)
uv run pytest -m unit

# Run integration tests (requires database)
uv run pytest -m integration

# Run end-to-end tests (requires database)
uv run pytest -m e2e

# Run slow tests (CLI tests)
uv run pytest -m slow

# Run everything except slow tests
uv run pytest -m "not slow"
```

### Specific Test Files

```bash
# Test API endpoints
uv run pytest tests/test_api_endpoints.py

# Test authentication
uv run pytest tests/test_auth_endpoints.py

# Test database connectivity
uv run pytest tests/test_supabase_connection.py

# Test DAO layer
uv run pytest tests/test_dao.py

# Test CLI functionality
uv run pytest tests/test_cli.py

# Test advanced workflows
uv run pytest tests/test_enhanced_e2e.py
```

### Test Runner Options

The custom test runner (`run_tests.py`) provides additional options:

```bash
# Show available options
uv run python run_tests.py --help

# Run specific categories
uv run python run_tests.py --category integration
uv run python run_tests.py --category e2e

# Generate coverage reports
uv run python run_tests.py --coverage --html-coverage --xml-coverage

# Run specific file or function
uv run python run_tests.py --file tests/test_api_endpoints.py
uv run python run_tests.py --function test_health_check

# Verbose output with fail-fast
uv run python run_tests.py --verbose --fail-fast

# Dry run (show commands without executing)
uv run python run_tests.py --dry-run --category e2e --coverage
```

## Test Coverage

### Coverage Configuration

Coverage is configured in `.coveragerc`:

- **Source**: Current directory (.)
- **Omits**: Test files, cache, virtual environments, scripts
- **Includes**: Branch coverage
- **Reports**: HTML in `htmlcov/`, XML in `coverage.xml`

### Coverage Commands

```bash
# Basic coverage
uv run pytest --cov=.

# Coverage with missing lines
uv run pytest --cov=. --cov-report=term-missing

# HTML coverage report
uv run pytest --cov=. --cov-report=html
open htmlcov/index.html

# XML coverage for CI
uv run pytest --cov=. --cov-report=xml

# Coverage with specific threshold
uv run pytest --cov=. --cov-fail-under=80
```

### Coverage Targets

Aim for these coverage levels:

- **Overall**: 80%+ (excluding scripts and utilities)
- **Core modules**: 90%+ (app.py, dao/)
- **API endpoints**: 95%+ (all endpoints tested)
- **Business logic**: 85%+ (DAO methods, calculations)

## Test Development

### Writing New Tests

1. **Follow the Pattern**: Use appropriate markers and fixtures
2. **Use Fixtures**: Leverage fixtures from `conftest.py`
3. **Handle Empty Data**: Tests should work with empty databases
4. **Add Documentation**: Include clear docstrings
5. **Test Error Cases**: Include error handling tests
6. **Aim for Coverage**: Cover new code with tests

### Example Test Structure

```python
@pytest.mark.integration
def test_new_functionality(test_client, enhanced_dao):
    """Test description explaining what this tests."""
    # Arrange
    test_data = {"key": "value"}
    
    # Act
    response = test_client.post("/api/endpoint", json=test_data)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### Test Categories Guidelines

#### Unit Tests (`@pytest.mark.unit`)
- Test individual functions/methods in isolation
- Use mocks for external dependencies
- Fast execution (< 1 second each)
- No database or network calls

#### Integration Tests (`@pytest.mark.integration`)
- Test database interactions
- Test DAO layer functionality
- Test component interactions
- Require database connection

#### End-to-End Tests (`@pytest.mark.e2e`)
- Test complete workflows
- Test API endpoints
- Test business logic validation
- Test data consistency across components

#### Slow Tests (`@pytest.mark.slow`)
- CLI tests with subprocess calls
- Tests that take > 5 seconds
- Performance tests
- System integration tests

## Continuous Integration

### CI Configuration

Example GitHub Actions configuration:

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install uv
      run: pip install uv
    
    - name: Install dependencies
      run: |
        cd backend
        uv sync --dev
    
    - name: Setup Supabase
      run: |
        cd backend
        npx supabase start
    
    - name: Run tests
      run: |
        cd backend
        python run_tests.py --category integration --coverage --xml-coverage
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
```

### CI Commands

```bash
# Quick smoke test for CI
uv run pytest -m "not slow" --tb=short

# Full test suite with coverage for CI
uv run pytest --cov=. --cov-report=xml --tb=short

# Integration tests only
uv run pytest -m integration --cov=. --cov-report=term

# Fail if coverage below threshold
uv run pytest --cov=. --cov-fail-under=80
```

## Troubleshooting

### Common Issues

#### "Local Supabase not running"
```bash
# Start Supabase
supabase start

# Check status
supabase status

# Ensure environment variables are set
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_KEY=your_key_here
```

#### "Tests failing with database errors"
```bash
# Reset database
supabase db reset

# Repopulate reference data
uv run python scripts/setup/populate_reference_data.py

# Check database connectivity
uv run pytest tests/test_supabase_connection.py::test_supabase_connection -v
```

#### "CLI tests timing out"
```bash
# Run CLI tests with longer timeout
uv run pytest tests/test_cli.py -v --tb=short

# Skip slow tests during development
uv run pytest -m "not slow"
```

#### "Coverage issues"
```bash
# Clean coverage data
rm -rf .coverage htmlcov/

# Ensure .coveragerc is properly configured
cat .coveragerc

# Re-run with fresh coverage
uv run pytest --cov=. --cov-report=html
```

### Debug Mode

```bash
# Run tests with verbose output
uv run pytest -v -s

# Run single test with debug
uv run pytest tests/test_api_endpoints.py::TestHealthCheck::test_health_check -v -s

# Show test collection without running
uv run pytest --collect-only

# Show fixtures
uv run pytest --fixtures
```

## Performance

### Test Execution Times

Typical execution times:

- **Unit tests**: < 10 seconds
- **Integration tests**: 10-30 seconds  
- **E2E tests**: 30-60 seconds
- **CLI tests**: 60-120 seconds
- **Full suite**: 2-5 minutes
- **With coverage**: +30-60 seconds

### Optimization Tips

1. **Use appropriate markers** to run only needed tests
2. **Run unit tests frequently** during development
3. **Use session-scoped fixtures** for expensive setup
4. **Skip slow tests** during rapid development
5. **Use parallel execution** for large test suites
6. **Mock external dependencies** in unit tests

## Best Practices

### Test Organization

1. **Group related tests** in classes
2. **Use descriptive test names** that explain what's being tested
3. **Follow AAA pattern**: Arrange, Act, Assert
4. **One assertion per test** when possible
5. **Test both success and failure cases**

### Test Data

1. **Use fixtures** for reusable test data
2. **Keep tests independent** - no shared state
3. **Test with realistic data** but avoid dependencies
4. **Handle empty data gracefully**
5. **Use factories** for complex test data generation

### Test Maintenance

1. **Keep tests simple** and focused
2. **Update tests** when changing functionality
3. **Remove obsolete tests** when removing features
4. **Monitor coverage** and add tests for uncovered code
5. **Review test failures** promptly

## Advanced Testing

### Load Testing

For load testing, consider using tools like:

- **Locust** for API load testing
- **pytest-benchmark** for performance testing
- **Apache Bench (ab)** for simple load tests

### Security Testing

Security testing considerations:

- Test authentication and authorization
- Validate input sanitization
- Test rate limiting
- Check for common vulnerabilities (SQL injection, XSS)
- Verify proper error handling

### Database Testing

Advanced database testing:

- Test transaction rollbacks
- Test concurrent access
- Validate data integrity constraints
- Test migration scripts
- Verify backup and restore procedures

## 🏥 Health Check Endpoints for Debugging

The backend provides two health check endpoints that are very useful for debugging:

### Basic Health Check
```bash
# Test basic API functionality
curl http://localhost:8000/health
```

### Comprehensive Health Check  
```bash
# Test full system health including database
curl http://localhost:8000/health/full

# Or with test client for detailed output
uv run python -c "
from fastapi.testclient import TestClient
from app import app
import json
client = TestClient(app)

print('=== Basic Health ===')
response = client.get('/health')
print(f'Status: {response.status_code}')
print(json.dumps(response.json(), indent=2))

print('\\n=== Full Health ===')  
response = client.get('/health/full')
print(f'Status: {response.status_code}')
print(json.dumps(response.json(), indent=2))
"
```

The full health check verifies:
- **API**: Basic API responsiveness
- **Database**: Supabase connection and basic queries  
- **Reference Data**: Essential data availability (seasons, game types, age groups)
- **Authentication**: Auth system functionality
- **Security**: Security monitoring status

**Response codes:**
- **200**: System healthy or degraded (check individual component status)
- **503**: Critical system failure (check `checks` object for details)

**Quick health check test:**
```bash
# Test health endpoints
uv run pytest tests/test_api_endpoints.py::test_health_check tests/test_api_endpoints.py::test_full_health_check -v
```

---

For more information, see:
- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Supabase Testing Guide](https://supabase.com/docs/guides/getting-started/local-development)
