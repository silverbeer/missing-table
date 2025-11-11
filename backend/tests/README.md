# Missing Table Backend Test Suite

Comprehensive testing documentation for the Missing Table backend application.

## 📋 Table of Contents

1. [Test Organization](#test-organization)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [Running Tests](#running-tests)
5. [Test Categories](#test-categories)
6. [Coverage Requirements](#coverage-requirements)
7. [CrewAI Agent Integration](#crewai-agent-integration)
8. [Writing Tests](#writing-tests)
9. [Troubleshooting](#troubleshooting)

---

## 🎯 Test Organization

The test suite is organized into five distinct layers, each with specific purposes and performance characteristics:

```
backend/tests/
├── unit/                      # Fast, isolated component tests
│   ├── dao/                   # Data access layer tests
│   ├── services/              # Business logic service tests
│   ├── models/                # Model validation tests
│   └── utils/                 # Utility function tests
│
├── integration/               # Component interaction tests
│   ├── api/                   # API endpoint tests (with TestClient)
│   ├── database/              # Database integration tests
│   └── auth/                  # Authentication flow tests
│
├── contract/                  # API contract tests (existing)
│   ├── test_auth_contract.py
│   ├── test_games_contract.py
│   └── test_schemathesis.py
│
├── e2e/                       # End-to-end user journey tests
│   ├── test_user_signup_flow.py
│   ├── test_match_management.py
│   └── test_admin_workflows.py
│
├── smoke/                     # Quick sanity checks for deployments
│   ├── test_health_checks.py
│   ├── test_critical_endpoints.py
│   └── test_database_connectivity.py
│
├── fixtures/                  # Shared test fixtures (if needed)
├── helpers/                   # Test utilities and helpers (if needed)
├── resources/                 # Test data and resources (if needed)
├── conftest.py                # Shared pytest configuration and fixtures
└── README.md                  # This file
```

---

## ✅ Prerequisites

### Required Software

- **Python 3.13+** (managed via `uv`)
- **Supabase** (local or cloud instance)
- **PostgreSQL** (via Supabase)
- **Redis** (optional, for some integration tests)

### Python Dependencies

All test dependencies are managed via `pyproject.toml`:

```bash
# Install dependencies
cd backend && uv sync

# Key testing dependencies:
# - pytest: Test framework
# - pytest-cov: Coverage reporting
# - pytest-xdist: Parallel test execution
# - pytest-asyncio: Async test support
# - faker: Test data generation
# - httpx: HTTP client for API testing
# - schemathesis: API contract testing
```

### Database Setup

**Local Supabase (Recommended for development):**

```bash
# Start local Supabase
cd supabase-local && npx supabase start

# Restore test data
./scripts/db_tools.sh restore

# Verify database is running
npx supabase status
```

**Cloud Supabase (For integration testing):**

```bash
# Switch to dev environment
./switch-env.sh dev

# Apply migrations
cd supabase-local && npx supabase db push --linked
```

---

## 🔐 Environment Variables

Tests use environment-specific configuration files:

### Environment File Hierarchy

```
Priority: .env.test > .env.e2e > .env (loaded in conftest.py)
```

### Required Environment Variables

Create `backend/.env.test` (or use `.env.e2e` for e2e tests):

```bash
# Test Mode Flag
TEST_MODE=true

# Supabase Configuration
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here

# API Configuration
API_BASE_URL=http://localhost:8000
FRONTEND_BASE_URL=http://localhost:8080

# Authentication
JWT_SECRET=your_test_jwt_secret
JWT_ALGORITHM=HS256

# Redis (Optional)
REDIS_URL=redis://localhost:6379

# Disable Security for Testing (Optional)
DISABLE_SECURITY=false
```

### Environment Variables in Tests

Access environment variables via fixtures in `conftest.py`:

```python
def test_api_endpoint(base_api_url, test_client):
    """base_api_url fixture provides the API_BASE_URL from environment."""
    response = test_client.get(f"{base_api_url}/api/version")
    assert response.status_code == 200
```

---

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
cd backend && uv run pytest

# Run with coverage
cd backend && uv run pytest --cov=. --cov-report=html

# Run specific test category
cd backend && uv run pytest -m unit           # Unit tests only
cd backend && uv run pytest -m integration    # Integration tests only
cd backend && uv run pytest -m contract       # Contract tests only
cd backend && uv run pytest -m e2e            # E2E tests only
cd backend && uv run pytest -m smoke          # Smoke tests only
```

### Advanced Test Execution

```bash
# Run tests in parallel (faster)
cd backend && uv run pytest -n auto

# Run tests with verbose output
cd backend && uv run pytest -v

# Run specific test file
cd backend && uv run pytest tests/unit/test_dao.py

# Run specific test function
cd backend && uv run pytest tests/unit/test_dao.py::test_get_team

# Run tests matching pattern
cd backend && uv run pytest -k "test_auth"

# Run tests with detailed output (no capture)
cd backend && uv run pytest -s

# Show slowest 10 tests
cd backend && uv run pytest --durations=10

# Skip slow tests
cd backend && uv run pytest -m "not slow"

# Run only failed tests from last run
cd backend && uv run pytest --lf

# Run failed tests first, then rest
cd backend && uv run pytest --ff
```

### Coverage-Specific Commands

```bash
# Generate HTML coverage report
cd backend && uv run pytest --cov=. --cov-report=html
# Open: backend/htmlcov/index.html

# Generate terminal report with missing lines
cd backend && uv run pytest --cov=. --cov-report=term-missing

# Generate JSON report (for CI/CD)
cd backend && uv run pytest --cov=. --cov-report=json

# Fail if coverage below threshold
cd backend && uv run pytest --cov=. --cov-fail-under=75

# Per-layer coverage enforcement
cd backend && uv run pytest tests/unit/ --cov=. --cov-fail-under=80
cd backend && uv run pytest tests/integration/ --cov=. --cov-fail-under=70
cd backend && uv run pytest tests/contract/ --cov=. --cov-fail-under=90
```

---

## 📊 Test Categories

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation

**Characteristics**:
- No external dependencies (databases, APIs)
- Use mocks and fixtures
- Fast execution (<100ms per test)
- High code coverage (80-90%)

**Example**:

```python
import pytest

@pytest.mark.unit
def test_calculate_standings():
    """Test standings calculation logic."""
    from services.standings_service import calculate_standings
    
    matches = [...]  # Mock data
    standings = calculate_standings(matches)
    
    assert standings[0]["team"] == "Team A"
    assert standings[0]["points"] == 9
```

### Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions

**Characteristics**:
- Tests API endpoints with TestClient
- Database interactions
- Authentication flows
- Moderate speed (<500ms per test)
- Coverage target: 70-80%

**Example**:

```python
import pytest

@pytest.mark.integration
@pytest.mark.requires_supabase
def test_get_teams_endpoint(test_client, base_api_url):
    """Test GET /api/teams endpoint."""
    response = test_client.get(f"{base_api_url}/api/teams")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
```

### Contract Tests (`tests/contract/`)

**Purpose**: Validate API contracts and schemas

**Characteristics**:
- Tests API specification compliance
- Schema validation
- Uses schemathesis
- Coverage target: 90-95%
- Speed: <1s per test

**Example**:

```python
import pytest
import schemathesis

@pytest.mark.contract
def test_api_schema_compliance():
    """Test API matches OpenAPI specification."""
    schema = schemathesis.from_uri("http://localhost:8000/openapi.json")
    
    @schema.parametrize()
    def test_api(case):
        case.call_and_validate()
```

### E2E Tests (`tests/e2e/`)

**Purpose**: Test complete user journeys

**Characteristics**:
- Full application flow
- Multiple components
- Real database operations
- Slow execution (<5s per test)
- Coverage target: 50-60%

**Example**:

```python
import pytest

@pytest.mark.e2e
@pytest.mark.requires_supabase
def test_user_signup_and_login_flow(test_client, faker_instance):
    """Test complete user signup and login journey."""
    # 1. Sign up new user
    email = faker_instance.email()
    response = test_client.post("/api/auth/signup", json={
        "email": email,
        "password": "TestPass123!",
        "display_name": "Test User"
    })
    assert response.status_code == 201
    
    # 2. Log in
    response = test_client.post("/api/auth/login", json={
        "email": email,
        "password": "TestPass123!"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # 3. Access protected resource
    headers = {"Authorization": f"Bearer {token}"}
    response = test_client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
```

### Smoke Tests (`tests/smoke/`)

**Purpose**: Quick sanity checks for deployments

**Characteristics**:
- Critical path only
- Fast execution (<2s per test)
- 100% coverage of critical endpoints
- Run before/after deployments

**Example**:

```python
import pytest

@pytest.mark.smoke
def test_api_health_check(test_client):
    """Test API is responsive."""
    response = test_client.get("/api/health")
    assert response.status_code == 200

@pytest.mark.smoke
def test_database_connectivity(supabase_client):
    """Test database is accessible."""
    result = supabase_client.table("teams").select("id").limit(1).execute()
    assert result.data is not None
```

---

## 📈 Coverage Requirements

### Per-Layer Coverage Targets

| Layer | Minimum | Target | Speed | Test Count Target |
|-------|---------|--------|-------|-------------------|
| **Unit** | 80% | 90% | <100ms/test | 200+ tests |
| **Integration** | 70% | 80% | <500ms/test | 100+ tests |
| **Contract** | 90% | 95% | <1s/test | 50+ tests |
| **E2E** | 50% | 60% | <5s/test | 20+ tests |
| **Smoke** | 100% | 100% | <2s/test | 10+ tests |

### Overall Project Coverage

- **Minimum**: 75% overall code coverage
- **Target**: 85% overall code coverage
- **Critical Paths**: 100% coverage (auth, payments, data integrity)

### Performance Benchmarks

- **Unit tests**: Full suite <10 seconds
- **Integration tests**: Full suite <2 minutes
- **Contract tests**: Full suite <2 minutes
- **E2E tests**: Full suite <5 minutes
- **Smoke tests**: Full suite <30 seconds

---

## 🤖 CrewAI Agent Integration

The Missing Table project uses CrewAI autonomous agents to generate and enhance tests.

### AI-Generated Test Marker

All AI-generated tests are marked with `@pytest.mark.ai_generated`:

```python
@pytest.mark.ai_generated
@pytest.mark.integration
def test_match_filtering(test_client):
    """Test generated by CrewAI FORGE agent."""
    response = test_client.get("/api/matches?age_group=U14")
    assert response.status_code == 200
```

### CrewAI Testing Agents

The CrewAI testing system consists of 8 specialized agents:

1. **SWAGGER** - API Documentation Expert
2. **ARCHITECT** - Test Scenario Designer
3. **MOCKER** - Test Data Craftsman
4. **FORGE** - Test Code Generator
5. **FLASH** - Test Executor
6. **INSPECTOR** - Quality Analyst
7. **HERALD** - Test Reporter
8. **SHERLOCK** - Test Debugger

### Running CrewAI Test Generation

```bash
# Show CrewAI status and agent roster
./crew_testing/status.sh

# Generate tests for an endpoint
./crew_testing/run.sh scan

# Verbose mode
./crew_testing/run.sh scan --verbose

# View CrewAI documentation
cat crew_testing/README.md
```

### CrewAI Configuration

Set up CrewAI API key in `.env.local`:

```bash
# Anthropic API Key (Claude 3 Haiku)
ANTHROPIC_API_KEY=sk-ant-api03-...

# CrewAI Configuration
CREW_VERBOSE=false
```

**Cost**: ~$0.05 per scan, ~$5/month in production

### How CrewAI Agents Hook In

1. **SWAGGER** scans OpenAPI spec and identifies endpoints
2. **ARCHITECT** designs comprehensive test scenarios
3. **MOCKER** generates realistic test data using Faker
4. **FORGE** creates pytest test files with proper markers
5. **FLASH** executes tests and captures results
6. **INSPECTOR** analyzes coverage and quality metrics
7. **HERALD** generates test reports
8. **SHERLOCK** debugs failing tests

Generated tests are saved to appropriate test directories:

```bash
# Unit tests
backend/tests/unit/ai_generated/

# Integration tests
backend/tests/integration/ai_generated/

# Contract tests
backend/tests/contract/ai_generated/
```

---

## ✍️ Writing Tests

### Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*` (if using classes)
- Test functions: `test_*`

### Using Fixtures

```python
import pytest

def test_with_fixtures(test_client, faker_instance, base_api_url):
    """Test using shared fixtures from conftest.py."""
    # faker_instance: Generate test data
    email = faker_instance.email()
    name = faker_instance.name()
    
    # test_client: FastAPI TestClient
    response = test_client.post(f"{base_api_url}/api/users", json={
        "email": email,
        "name": name
    })
    
    assert response.status_code == 201
```

### Available Fixtures (from conftest.py)

**Configuration Fixtures**:
- `base_api_url`: API base URL
- `base_frontend_url`: Frontend base URL
- `supabase_url`: Supabase URL
- `supabase_anon_key`: Supabase anon key
- `supabase_service_key`: Supabase service key

**Client Fixtures**:
- `test_client`: FastAPI TestClient
- `supabase_client`: Supabase client
- `enhanced_dao`: DAO instance

**Test Data Generation**:
- `faker_instance`: Shared Faker instance (reproducible)
- `faker_factory`: Factory for fresh Faker instances

**Authentication**:
- `auth_headers`: Mock auth headers
- `mock_auth_headers`: Role-based auth headers
- `admin_user_data`: Admin user sample data
- `team_manager_user_data`: Team manager sample data
- `regular_user_data`: Regular user sample data

**Sample Data**:
- `sample_team_data`: Sample team data
- `sample_game_data`: Sample game data
- `valid_team_data`: Valid team creation data
- `valid_game_data`: Valid game creation data

**Utilities**:
- `database_cleanup`: Cleanup fixture
- `mock_security_disabled`: Disable security for testing

### Test Structure Best Practices

```python
import pytest

@pytest.mark.unit  # Add appropriate marker
def test_feature_name():
    """Clear docstring describing what is tested."""
    # Arrange: Set up test data
    data = {"key": "value"}
    
    # Act: Execute the test
    result = function_under_test(data)
    
    # Assert: Verify the outcome
    assert result == expected_value
```

---

## 🧰 Test Fixtures & Utilities

The test suite includes comprehensive fixtures, factories, and utilities to make tests deterministic, maintainable, and consistent.

### Complete Guide

**📖 [FIXTURES_AND_UTILITIES_GUIDE.md](docs/04-testing/FIXTURES_AND_UTILITIES_GUIDE.md)**

This comprehensive guide covers:
- Test data seeds (JSON files)
- Test factories (Faker-based)
- Custom assertions
- Test client utilities
- Database setup scripts
- Usage examples
- Best practices

### Quick Reference

**Test Data Seeds**:
```
tests/fixtures/data/
├── reference_data.json   # Age groups, divisions, seasons, match types
├── teams.json            # Sample team data
└── users.json            # Test user accounts
```

**Factories** (`tests/fixtures/factories.py`):
```python
from tests.fixtures.factories import TeamFactory, MatchFactory, UserFactory

# Create test entities with deterministic data
team = TeamFactory.create(name="Test FC", city="Boston, MA")
match = MatchFactory.upcoming(home_team_id=1, away_team_id=2)
user = UserFactory.admin(email="admin@test.com")
```

**Custom Assertions** (`tests/utils/assertions.py`):
```python
from tests.utils.assertions import assert_valid_response, assert_valid_team

# Validate responses and data structures
assert_valid_response(response, status_code=200)
assert_valid_team(team_data, strict=True)
```

**Test Clients** (`tests/fixtures/clients.py`):
```python
from tests.fixtures.clients import create_admin_client, create_authenticated_client

# Create pre-configured test clients
admin_client = create_admin_client()
user_client = create_authenticated_client(user_id="test-123", role="user")
```

**Database Setup** (`scripts/test-db-setup.sh`):
```bash
# Setup database for specific test layer
./scripts/test-db-setup.sh integration
./scripts/test-db-setup.sh e2e
./scripts/test-db-setup.sh contract
```

### Why Use Fixtures & Utilities?

✅ **Deterministic**: Seeded Faker for reproducible tests
✅ **DRY**: Centralized test data generation
✅ **Maintainable**: Single source of truth
✅ **Consistent**: Standardized assertions
✅ **Isolated**: Per-layer database setup

See the complete guide for detailed usage examples and best practices.

---

## 🔧 Troubleshooting

### Common Issues

**1. Import Errors**

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/Users/silverbeer/gitrepos/missing-table/backend:$PYTHONPATH

# Or run pytest from backend directory
cd backend && uv run pytest
```

**2. Database Connection Errors**

```bash
# Check if Supabase is running
npx supabase status

# Restart Supabase
npx supabase stop && npx supabase start

# Verify connection
curl http://127.0.0.1:54321/rest/v1/
```

**3. Tests Skipped (Supabase not available)**

```bash
# Check TEST_MODE environment variable
echo $TEST_MODE  # Should be "true"

# Start Supabase
cd supabase-local && npx supabase start
```

**4. Coverage Not Generated**

```bash
# Install pytest-cov
uv add --dev pytest-cov

# Run with coverage flag
uv run pytest --cov=.
```

**5. Parallel Test Failures**

```bash
# Run tests sequentially (disable xdist)
uv run pytest -n 0

# Or disable parallel execution in pytest.ini
# Remove: -n auto
```

### Debug Mode

```bash
# Run with verbose output and no capture
cd backend && uv run pytest -v -s

# Show local variables in tracebacks
cd backend && uv run pytest --showlocals

# Enter debugger on failure
cd backend && uv run pytest --pdb
```

### Viewing Logs

Test logs are written to:

```bash
# Pytest logs
backend/logs/pytest.log

# View real-time logs
tail -f backend/logs/pytest.log
```

---

## 📚 Additional Resources

### Test Infrastructure Documentation
- **Fixtures & Utilities Guide**: [docs/04-testing/FIXTURES_AND_UTILITIES_GUIDE.md](docs/04-testing/FIXTURES_AND_UTILITIES_GUIDE.md) ⭐
- **Testing Strategy**: [docs/04-testing/TEST_ORGANIZATION_PLAN.md](../../docs/04-testing/TEST_ORGANIZATION_PLAN.md)
- **Migration Complete**: [docs/04-testing/MIGRATION_COMPLETE.md](docs/04-testing/MIGRATION_COMPLETE.md)
- **Post-Migration Verification**: [docs/04-testing/POST_MIGRATION_VERIFICATION.md](docs/04-testing/POST_MIGRATION_VERIFICATION.md)
- **Migration Mapping**: [docs/04-testing/test-migration-mapping.csv](../../docs/04-testing/test-migration-mapping.csv)

### External Documentation
- **pytest Documentation**: https://docs.pytest.org/
- **Coverage.py Documentation**: https://coverage.readthedocs.io/
- **Schemathesis Documentation**: https://schemathesis.readthedocs.io/
- **Faker Documentation**: https://faker.readthedocs.io/
- **CrewAI Documentation**: [crew_testing/README.md](../../crew_testing/README.md)

---

**Last Updated**: 2025-11-11  
**Maintained By**: Backend Team  
**Questions?** See [docs/10-contributing/README.md](../../docs/10-contributing/README.md)
