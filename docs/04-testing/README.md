# 🧪 Testing & Quality Documentation

> **Audience**: Developers, QA engineers, contributors
> **Prerequisites**: [Getting Started](../01-getting-started/) completed
> **Goal**: Zero failed tests, 80%+ code coverage

This section covers the testing strategy, tools, and quality metrics for the Missing Table project.

---

## 📚 Documentation in This Section

| Document | Description | Difficulty |
|----------|-------------|------------|
| **[Testing Strategy](testing-strategy.md)** | Overall testing approach and goals | 🟢 Beginner |
| **[Backend Testing](backend-testing.md)** | Pytest, fixtures, coverage | 🟡 Intermediate |
| **[Frontend Testing](frontend-testing.md)** | Jest, Vue Test Utils | 🟡 Intermediate |
| **[API Contract Testing](api-contract-testing.md)** | Schemathesis, contract validation | 🔴 Advanced |
| **[Quality Metrics](quality-metrics.md)** | Coverage goals, quality gates | 🟢 Beginner |
| **[Test Results](test-results/)** | Historical test reports | 🟢 Beginner |

---

## 🎯 Testing Goals

### Primary Objectives

✅ **Zero Failed Tests** - All tests pass on every commit
✅ **High Code Coverage** - 80%+ across codebase
✅ **Clean CI/CD** - No failed workflow runs
✅ **Fast Feedback** - Tests run in < 5 minutes

### Current Status

**As of 2025-10-07:**
- ✅ Repository cleaned - all failed workflows deleted
- ✅ Zero failed tests achieved
- 🎯 Working towards 80% coverage
- ✅ Test baseline established

See: [Test Results](test-results/)

---

## 🚀 Quick Start

### Running Tests

```bash
# Backend tests (fast)
cd backend
uv run pytest                    # All tests
uv run pytest -m unit            # Unit tests only
uv run pytest -m integration     # Integration tests
uv run pytest --cov=.            # With coverage

# Frontend tests
cd frontend
npm test                         # All tests
npm run test:watch               # Watch mode
npm run test:coverage            # With coverage

# Run everything (from root)
./run-tests.sh                   # Helper script
```

### Before Committing

```bash
# Run pre-commit checks
cd backend && uv run pytest
cd frontend && npm test
cd frontend && npm run lint
```

---

## 📊 Test Structure

### Backend Test Organization

```
backend/tests/
├── unit/                 # Fast, isolated tests
│   ├── test_auth.py
│   ├── test_games.py
│   └── test_standings.py
├── integration/          # Database/API tests
│   ├── test_api_auth.py
│   ├── test_api_games.py
│   └── test_database.py
├── e2e/                  # Full workflow tests
│   └── test_user_workflows.py
├── contract/             # API contract tests
│   └── test_auth_contract.py
└── conftest.py          # Pytest fixtures
```

### Frontend Test Organization

```
frontend/tests/
├── unit/
│   ├── components/       # Component tests
│   ├── stores/          # Store tests
│   └── utils/           # Utility tests
├── integration/         # Component integration
└── e2e/                 # Playwright tests (planned)
```

---

## 🏆 Coverage Goals

### Backend Coverage Targets

```
Overall:             80%+
Critical paths:      95%+

Specific modules:
- Authentication:    95%
- Game management:   90%
- Standings calc:    95%
- Admin operations:  85%
- DAO layer:         90%
```

### Frontend Coverage Targets

```
Overall:             80%+

By type:
- Components:        75%+
- Stores:            90%+
- Utils:             85%+
- Router:            70%+
```

### Checking Coverage

```bash
# Backend - View in browser
cd backend
uv run pytest --cov=. --cov-report=html
open htmlcov/index.html

# Frontend - View in browser
cd frontend
npm run test:coverage
open coverage/lcov-report/index.html
```

---

## 🔬 Test Types

### 1. Unit Tests
**Purpose**: Test individual functions/classes in isolation

**Characteristics**:
- ⚡ Very fast (< 1 second each)
- 🔒 No external dependencies
- 🎯 Focused on single responsibility
- 🧪 Use mocks for dependencies

**Example**:
```python
@pytest.mark.unit
def test_calculate_points():
    """Test points calculation for a win."""
    result = calculate_points(wins=3, draws=1, losses=0)
    assert result == 10  # 3*3 + 1*1
```

### 2. Integration Tests
**Purpose**: Test component interactions, database operations

**Characteristics**:
- 🐢 Slower (1-5 seconds each)
- 🗄️ Requires database connection
- 🔗 Tests multiple components together
- 📊 Verifies data persistence

**Example**:
```python
@pytest.mark.integration
def test_create_game(test_client, enhanced_dao):
    """Test game creation via API."""
    response = test_client.post("/api/games", json=game_data)
    assert response.status_code == 200
    # Verify in database
    game = enhanced_dao.get_game(response.json()["id"])
    assert game is not None
```

### 3. End-to-End (E2E) Tests
**Purpose**: Test complete user workflows

**Characteristics**:
- 🐌 Slowest (5-30 seconds each)
- 🌐 Tests full stack
- 👤 Simulates user behavior
- ✅ Verifies business logic

**Example**:
```python
@pytest.mark.e2e
def test_user_login_flow(test_client):
    """Test complete login workflow."""
    # Signup
    signup_response = test_client.post("/api/auth/signup", ...)
    # Login
    login_response = test_client.post("/api/auth/login", ...)
    # Access protected resource
    protected_response = test_client.get("/api/profile", ...)
    assert all responses successful
```

### 4. Contract Tests
**Purpose**: Verify API adheres to OpenAPI specification

**Characteristics**:
- 🔍 Validates request/response schemas
- 📝 Ensures API documentation accuracy
- 🛡️ Catches breaking changes
- 🤖 Automated with Schemathesis

See: [API Contract Testing](api-contract-testing.md)

---

## ⚡ Running Tests Efficiently

### Test Markers

```bash
# Run by marker
uv run pytest -m unit              # Only unit tests (fast)
uv run pytest -m integration       # Only integration tests
uv run pytest -m "not slow"        # Exclude slow tests
uv run pytest -m e2e               # Only E2E tests

# Multiple markers
uv run pytest -m "unit or integration"
```

### Useful Options

```bash
# Fail fast - stop on first failure
uv run pytest -x

# Verbose output
uv run pytest -v

# Show local variables on failure
uv run pytest -l

# Run specific test
uv run pytest tests/test_auth.py::test_login

# Run tests matching pattern
uv run pytest -k "test_login"

# Parallel execution (if installed pytest-xdist)
uv run pytest -n auto
```

---

## 📈 Quality Gates

### Required for PR Merge

- ✅ All tests passing
- ✅ No decrease in code coverage (max 2% drop allowed)
- ✅ Security scans pass
- ✅ Code review approved
- ✅ No linting errors

### CI/CD Pipeline

**On Pull Request:**
1. Run all backend tests
2. Run all frontend tests
3. Check code coverage
4. Run security scans
5. Lint code

**On Merge to Main:**
1. Full test suite
2. Deploy to dev environment
3. Run smoke tests
4. Update coverage reports

See: [CI/CD Documentation](../09-cicd/)

---

## 🎓 Writing Good Tests

### Best Practices

**DO:**
- ✅ Test behavior, not implementation
- ✅ Use descriptive test names
- ✅ Follow AAA pattern (Arrange, Act, Assert)
- ✅ Keep tests independent
- ✅ Test edge cases and errors
- ✅ Use fixtures for common setup

**DON'T:**
- ❌ Test framework code
- ❌ Make tests depend on each other
- ❌ Use sleep() for timing
- ❌ Ignore failing tests
- ❌ Test too many things in one test

### Test Naming Convention

```python
def test_<function>_<scenario>_<expected_result>():
    """Clear description of what this tests."""

# Examples:
def test_login_valid_credentials_returns_token():
def test_create_game_missing_data_returns_422():
def test_calculate_standings_empty_games_returns_empty():
```

### AAA Pattern

```python
def test_example():
    # Arrange - Setup test data and conditions
    user = create_test_user()
    game_data = {"home_team": 1, "away_team": 2}

    # Act - Execute the code being tested
    result = create_game(game_data)

    # Assert - Verify the result
    assert result.home_team_id == 1
    assert result.status == "scheduled"
```

---

## 🔧 Testing Tools

### Backend
- **pytest** - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-asyncio** - Async test support
- **Schemathesis** - API contract testing
- **respx** - HTTP mocking

### Frontend
- **Jest** - Test framework
- **Vue Test Utils** - Component testing
- **@testing-library/vue** - User-centric testing
- **Playwright** - E2E testing (planned)

### CI/CD
- **GitHub Actions** - Automation
- **Codecov** - Coverage tracking (planned)
- **SonarQube** - Code quality (planned)

---

## 📖 Related Documentation

- **[Development Guide](../02-development/)** - Development workflow
- **[Architecture](../03-architecture/)** - System design
- **[CI/CD](../09-cicd/)** - Automation pipeline
- **[Contributing](../10-contributing/)** - Contributing guidelines

---

## 🆘 Troubleshooting

### Tests Failing Locally

```bash
# Ensure database is running
supabase status

# Reset database
supabase db reset

# Restore test data
./scripts/db_tools.sh restore

# Clear pytest cache
rm -rf .pytest_cache
```

### Coverage Issues

```bash
# Clean coverage data
rm -rf .coverage htmlcov/

# Regenerate coverage
uv run pytest --cov=. --cov-report=html
```

### Slow Tests

```bash
# Find slow tests
uv run pytest --durations=10

# Run only fast tests during development
uv run pytest -m "not slow"
```

---

<div align="center">

**Current Status**: ✅ Zero failed tests | 🎯 Working towards 80% coverage

[⬆ Back to Documentation Hub](../README.md)

</div>
