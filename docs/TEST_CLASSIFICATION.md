# Test Classification & Pyramid Visualization

**Date:** 2025-10-07
**Purpose:** Establish test taxonomy and visualization for quality metrics

---

## Overview

This document defines the test classification system for Missing Table, enabling:
- 🏷️ **Multi-dimensional test tagging** - Classify tests by pyramid level, stack, module, performance
- 🏔️ **Test pyramid visualization** - See test distribution across pyramid levels
- 📊 **Quality metrics** - Track pass/fail rates at each level
- 🎯 **Targeted test execution** - Run specific test subsets efficiently

---

## Test Pyramid Philosophy

```
                    /\
                   /  \          🔺 E2E Tests (Few)
                  /____\         - Full user workflows
                 /      \        - Slowest, most expensive
                /________\       - Highest confidence
               /          \
              /   CONTRACT \     🔶 Contract Tests
             /______________\    - API interface validation
            /                \
           /   INTEGRATION    \  🔷 Integration Tests
          /____________________\ - Multiple components
         /                      \
        /       COMPONENT        \ 🔸 Component Tests (Frontend)
       /_________________________ - UI component testing
      /                           \
     /          UNIT TESTS          \ 🟦 Unit Tests (Many)
    /_______________________________\ - Pure logic, fast
                                      - Most tests should be here
```

### Pyramid Guidelines

1. **Unit Tests (Base)** - 60-70% of tests
   - Fast (< 100ms each)
   - No dependencies
   - Pure logic testing
   - Mocked external calls

2. **Component Tests** (Frontend) - 15-20% of tests
   - UI component behavior
   - User interactions
   - Component composition
   - Snapshot testing

3. **Integration Tests** - 10-15% of tests
   - Multiple components working together
   - Database interactions
   - API endpoint testing
   - Service integration

4. **Contract Tests** - 5-10% of tests
   - API request/response validation
   - Schema validation
   - Backward compatibility

5. **E2E Tests (Top)** - 5-10% of tests
   - Complete user workflows
   - Browser automation
   - Critical paths only
   - Most expensive/slowest

---

## Classification Dimensions

### 1. Pyramid Level (Primary)

**Markers:** `@pytest.mark.{level}` or `describe('[{level}]')`

| Marker | Description | Speed | Dependencies | Examples |
|--------|-------------|-------|--------------|----------|
| `unit` | Pure logic, no deps | < 100ms | None | Calculate points, format date |
| `component` | UI components | < 500ms | DOM only | LoginForm render, button click |
| `integration` | Multiple parts | 1-5s | DB, services | Login flow, game creation |
| `contract` | API validation | 1-3s | Server | API response structure |
| `e2e` | Full workflows | 5-30s | Everything | User signup → game entry |

### 2. Stack Location

**Markers:** `@pytest.mark.backend` or `@pytest.mark.frontend`

| Marker | Description | Language | Framework |
|--------|-------------|----------|-----------|
| `backend` | Python tests | Python 3.13+ | pytest |
| `frontend` | JavaScript tests | ES6+ | Vitest (planned) |

### 3. Module/Feature Area

**Markers:** `@pytest.mark.{module}`

| Marker | Description | Components |
|--------|-------------|------------|
| `auth` | Authentication | Login, signup, JWT, roles |
| `dao` | Data access | Database queries, ORM |
| `api` | API endpoints | FastAPI routes, responses |
| `invite` | Invite system | Invite creation, validation |
| `games` | Game management | CRUD, validation, scoring |
| `standings` | League tables | Calculations, sorting |
| `admin` | Admin functions | User mgmt, permissions |

### 4. Performance

**Markers:** `@pytest.mark.{speed}`

| Marker | Description | Typical Duration |
|--------|-------------|------------------|
| `fast` | Quick tests | < 100ms |
| `slow` | Long-running tests | > 1 second |

### 5. Dependencies

**Markers:** `@pytest.mark.{dependency}`

| Marker | Description | Required Setup |
|--------|-------------|----------------|
| `database` | Needs database | Supabase running |
| `server` | Needs API server | Backend running |
| `mock` | Uses mocks only | None |
| `external` | External services | Internet, APIs |

---

## Usage Examples

### Backend (pytest)

```python
# Unit test - pure logic
@pytest.mark.unit
@pytest.mark.backend
@pytest.mark.games
@pytest.mark.fast
@pytest.mark.mock
def test_calculate_team_points():
    """Test points calculation logic."""
    result = calculate_points(wins=3, draws=1, losses=0)
    assert result == 10

# Integration test - database + logic
@pytest.mark.integration
@pytest.mark.backend
@pytest.mark.dao
@pytest.mark.slow
@pytest.mark.database
def test_get_league_standings_from_db():
    """Test standings retrieval from database."""
    standings = dao.get_league_table(season_id=1)
    assert len(standings) > 0
    assert standings[0]['position'] == 1

# Contract test - API validation
@pytest.mark.contract
@pytest.mark.backend
@pytest.mark.api
@pytest.mark.auth
@pytest.mark.server
def test_login_endpoint_contract():
    """Validate login API response structure."""
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'password123'  # pragma: allowlist secret
    })
    assert response.status_code == 200
    assert 'access_token' in response.json()
    assert 'user' in response.json()

# E2E test - full workflow
@pytest.mark.e2e
@pytest.mark.backend
@pytest.mark.invite
@pytest.mark.slow
@pytest.mark.server
@pytest.mark.database
def test_complete_invite_workflow():
    """Test complete invite creation to signup flow."""
    # Admin creates invite
    invite = create_invite_as_admin(...)

    # New user receives code
    code = invite['code']

    # User signs up with code
    signup_response = signup_with_invite(code, ...)

    # User can login
    login_response = login(...)

    assert login_response.status_code == 200
```

### Frontend (Vitest - planned)

```javascript
// Unit test - pure logic
describe('[unit][frontend][utils]', () => {
  it('formats date correctly', () => {
    const result = formatDate('2025-10-07')
    expect(result).toBe('October 7, 2025')
  })
})

// Component test - UI
describe('[component][frontend][auth]', () => {
  it('LoginForm renders with email input', () => {
    const wrapper = mount(LoginForm)
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
  })

  it('LoginForm shows error on invalid input', async () => {
    const wrapper = mount(LoginForm)
    await wrapper.find('form').trigger('submit')
    expect(wrapper.find('.error-message').exists()).toBe(true)
  })
})

// Integration test - component + store
describe('[integration][frontend][auth]', () => {
  it('LoginForm updates auth store on success', async () => {
    const wrapper = mount(LoginForm)
    const authStore = useAuthStore()

    await wrapper.find('#email').setValue('test@example.com')
    await wrapper.find('#password').setValue('password123')
    await wrapper.find('form').trigger('submit')

    expect(authStore.isAuthenticated).toBe(true)
  })
})
```

---

## Running Tests by Classification

### By Pyramid Level

```bash
# Run only unit tests (fastest)
cd backend && uv run pytest -m unit

# Run only integration tests
cd backend && uv run pytest -m integration

# Run only contract tests
cd backend && uv run pytest -m contract

# Run only E2E tests
cd backend && uv run pytest -m e2e
```

### By Stack

```bash
# Backend tests only
cd backend && uv run pytest -m backend

# Frontend tests only (when set up)
cd frontend && npm run test -- --grep="\\[frontend\\]"
```

### By Module

```bash
# All auth tests
cd backend && uv run pytest -m auth

# All invite tests
cd backend && uv run pytest -m invite

# All DAO tests
cd backend && uv run pytest -m dao
```

### By Performance

```bash
# Fast tests only (< 100ms)
cd backend && uv run pytest -m fast

# Exclude slow tests
cd backend && uv run pytest -m "not slow"

# Only slow tests
cd backend && uv run pytest -m slow
```

### Combined Filters

```bash
# Fast backend unit tests
cd backend && uv run pytest -m "unit and backend and fast"

# Auth integration tests that need database
cd backend && uv run pytest -m "integration and auth and database"

# All tests except slow E2E
cd backend && uv run pytest -m "not (e2e and slow)"
```

---

## Test Pyramid Visualization

### Using the Pyramid Tool

```bash
# Run tests and show pyramid
cd backend && python test_pyramid.py

# Use existing test results
cd backend && python test_pyramid.py --no-run

# Export as JSON
cd backend && python test_pyramid.py --json > pyramid_report.json
```

### Example Output

```
================================================================================
🏔️  TEST PYRAMID VISUALIZATION
================================================================================

        🔺 E2E Tests                ✅
           ✅✅⏭️
           Total:   5 | ✅   3 | ❌   0 | ⏭️   2 |  60.0% pass

    🔶 Contract Tests           ❌
       ✅✅✅✅❌❌
       Total:  12 | ✅   8 | ❌   4 | ⏭️   0 |  66.7% pass

🔷 Integration Tests         ✅
   ✅✅✅✅✅✅✅✅✅✅⏭️
   Total:  28 | ✅  26 | ❌   0 | ⏭️   2 |  92.9% pass

    🔸 Component Tests          ⚪

       Total:   0 | ✅   0 | ❌   0 | ⏭️   0 |   0.0% pass

🟦 Unit Tests                  ✅
   ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅❌❌❌
   Total: 146 | ✅ 143 | ❌   3 | ⏭️   0 |  97.9% pass

================================================================================
📊 OVERALL: 191 tests | ✅ 180 passed | ❌ 7 failed | ⏭️ 4 skipped
   Pass Rate: 94.2%
================================================================================

📚 STACK DISTRIBUTION
--------------------------------------------------------------------------------
🐍 Backend       | ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅❌❌
   Total: 191 | ✅ 180 | ❌   7 |  94.2% pass

🎨 Frontend      |
   Total:   0 | ✅   0 | ❌   0 |   0.0% pass

🎯 MODULE DISTRIBUTION
--------------------------------------------------------------------------------
  invite       | ✅✅✅✅✅✅✅✅✅✅✅✅✅❌❌❌❌❌
   Total:  47 | ✅  39 | ❌   8 |  83.0% pass

  dao          | ✅✅✅✅✅✅✅✅✅✅❌❌❌❌
   Total:  28 | ✅  21 | ❌   7 |  75.0% pass

  auth         | ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
   Total:  23 | ✅  23 | ❌   0 | 100.0% pass
```

---

## Test Metadata in CI/CD

### GitHub Actions Integration

```yaml
# .github/workflows/test-pyramid.yml
name: Test Pyramid Report

on: [push, pull_request]

jobs:
  test-pyramid:
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

      - name: Run Test Pyramid
        run: |
          cd backend
          python test_pyramid.py --json > pyramid_report.json

      - name: Upload Pyramid Report
        uses: actions/upload-artifact@v3
        with:
          name: test-pyramid-report
          path: backend/pyramid_report.json

      - name: Comment PR with Pyramid
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs')
            const report = JSON.parse(fs.readFileSync('backend/pyramid_report.json'))

            const body = `## 🏔️ Test Pyramid Report

            **Overall:** ${report.total} tests | ✅ ${report.passed} | ❌ ${report.failed}

            **By Level:**
            - 🔺 E2E: ${report.by_level.e2e?.total || 0}
            - 🔶 Contract: ${report.by_level.contract?.total || 0}
            - 🔷 Integration: ${report.by_level.integration?.total || 0}
            - 🔸 Component: ${report.by_level.component?.total || 0}
            - 🟦 Unit: ${report.by_level.unit?.total || 0}
            `

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            })
```

---

## Migration Plan

### Phase 1: Tag Existing Tests (This Week)
```bash
# Audit current tests and add missing markers
cd backend

# Check which tests lack pyramid level markers
uv run pytest --collect-only -q | grep -v "@pytest.mark"

# Add markers to tests systematically:
# 1. contract/* → @pytest.mark.contract
# 2. test_dao.py → @pytest.mark.unit + @pytest.mark.dao
# 3. test_*_e2e.py → @pytest.mark.e2e
# 4. test_api_*.py → @pytest.mark.integration
```

### Phase 2: Frontend Setup (Week 2)
```bash
# Set up Vitest with describe block naming convention
cd frontend
npm install --save-dev vitest @vue/test-utils@next

# Configure vitest.config.js with test naming patterns
# Write example tests with [level][stack][module] pattern
```

### Phase 3: Visualization (Week 3)
```bash
# Run pyramid tool in CI/CD
# Add pyramid badge to README
# Track pyramid metrics over time
```

---

## Quality Gates

### Required Pyramid Balance

**Target Distribution:**
- Unit: 60-70% (currently need more)
- Component: 15-20% (frontend: 0%, need to create)
- Integration: 10-15% (good)
- Contract: 5-10% (good)
- E2E: 5-10% (need more)

**Quality Thresholds:**
- Unit tests: 95%+ pass rate
- Integration: 90%+ pass rate
- Contract: 95%+ pass rate
- E2E: 90%+ pass rate (acceptable to have some skipped)

---

## Best Practices

### 1. Always Tag Tests
```python
# ❌ Bad - no markers
def test_something():
    pass

# ✅ Good - properly classified
@pytest.mark.unit
@pytest.mark.backend
@pytest.mark.games
@pytest.mark.fast
def test_calculate_points():
    pass
```

### 2. One Primary Level Only
```python
# ❌ Bad - conflicting levels
@pytest.mark.unit
@pytest.mark.integration
def test_something():
    pass

# ✅ Good - one pyramid level
@pytest.mark.integration
@pytest.mark.backend
def test_game_creation_flow():
    pass
```

### 3. Use Performance Markers
```python
# ✅ Good - marks slow tests
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.database
def test_complex_query():
    pass
```

### 4. Document Test Purpose
```python
@pytest.mark.unit
@pytest.mark.backend
@pytest.mark.standings
def test_calculate_goal_difference():
    """
    Unit test: Pure calculation logic
    Tests goal difference calculation without database
    """
    pass
```

---

## Resources

- [Test Pyramid - Martin Fowler](https://martinfowler.com/bliki/TestPyramid.html)
- [Pytest Markers Documentation](https://docs.pytest.org/en/stable/how-to/mark.html)
- [Vitest API](https://vitest.dev/api/)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-07
**Next Review:** After Phase 1 migration complete
