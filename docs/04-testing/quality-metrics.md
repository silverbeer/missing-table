# Quality Initiative: Zero Failed Tests

**Branch:** `feature/zero-failed-tests`
**Started:** 2025-10-07
**Goal:** Achieve and maintain zero failed tests with high code coverage

## Objectives

### Primary Goal
🎯 **Zero Failed Tests** - All tests must pass on every commit

### Secondary Goals
- 📊 **Establish Baseline** - Document current test coverage
- 🔧 **Fix Failing Tests** - Resolve all existing test failures
- 📈 **Increase Coverage** - Target 60%+ coverage to start
- 🛠️ **Improve Tooling** - Make testing easy and automatic

## Current Status

### Repository State
- ✅ Clean workflow runs (0 failed)
- ✅ Testing strategy documented
- ⚠️ Test coverage unknown (need baseline)
- ⚠️ Individual test status unknown

### Test Infrastructure
- **Backend:** pytest with pytest-cov
- **Frontend:** Jest with Vue Test Utils
- **Contract:** Schemathesis (disabled)
- **E2E:** Playwright (planned)

## Roadmap

### Phase 1: Assessment (Week 1)
**Goal:** Understand current state

- [ ] Run all backend tests
- [ ] Run all frontend tests
- [ ] Generate coverage reports
- [ ] Document failing tests
- [ ] Document coverage baseline
- [ ] Identify gaps in test coverage

**Deliverables:**
- Coverage baseline report
- List of failing tests
- Gap analysis document

### Phase 2: Fix & Stabilize (Week 2-3)
**Goal:** Achieve zero failed tests

- [ ] Fix all failing backend tests
- [ ] Fix all failing frontend tests
- [ ] Add missing critical tests
- [ ] Verify all tests pass locally
- [ ] Verify all tests pass in CI

**Deliverables:**
- All tests passing
- Updated test documentation
- Test fixes committed

### Phase 3: Coverage Improvement (Week 4-6)
**Goal:** Reach 60%+ coverage

- [ ] Identify untested critical paths
- [ ] Add tests for authentication
- [ ] Add tests for game management
- [ ] Add tests for standings calculation
- [ ] Add tests for Vue components
- [ ] Add tests for stores

**Target Coverage:**
```
Backend:     60%+ (stepping stone to 80%)
Frontend:    60%+ (stepping stone to 80%)
Critical:    80%+ (auth, games, standings)
```

### Phase 4: Automation & Quality Gates (Week 7-8)
**Goal:** Make testing automatic and enforced

- [ ] Create run-tests.sh helper script
- [ ] Set up pre-commit hooks
- [ ] Configure GitHub Actions quality gates
- [ ] Add coverage badges
- [ ] Enable PR coverage checks
- [ ] Document testing workflow

**Deliverables:**
- Automated test running
- Quality gates enforced
- Developer documentation

## Testing Checklist

### Backend Tests
```bash
# Location: backend/tests/

# Run all tests
cd backend && uv run pytest

# Run with coverage
cd backend && uv run pytest --cov=. --cov-report=html --cov-report=term

# Run specific test file
cd backend && uv run pytest tests/test_auth.py

# Run with verbose output
cd backend && uv run pytest -v
```

### Frontend Tests
```bash
# Location: frontend/tests/

# Run all tests
cd frontend && npm test

# Run with coverage
cd frontend && npm run test:coverage

# Run in watch mode
cd frontend && npm run test:watch

# Run specific test
cd frontend && npm test -- LoginForm.spec.js
```

### Quick Test Script (To Be Created)
```bash
# Run all tests quickly
./run-tests.sh

# Run only backend
./run-tests.sh backend

# Run only frontend
./run-tests.sh frontend

# Run with coverage
./run-tests.sh --coverage
```

## Critical Test Areas

### Backend Priority Tests
1. **Authentication** (Critical - 95% target)
   - User login/logout
   - JWT token validation
   - Role-based access control
   - Invite code validation

2. **Game Management** (High - 90% target)
   - Add/edit/delete games
   - Game status updates
   - Duplicate detection
   - Validation rules

3. **Standings Calculation** (Critical - 95% target)
   - Points calculation
   - Goal difference
   - Team statistics
   - Filtering by season/division

4. **Admin Operations** (Medium - 85% target)
   - User management
   - Invite creation
   - Team management

### Frontend Priority Tests
1. **Components** (High - 75% target)
   - LeagueTable.vue
   - GameForm.vue
   - LoginForm.vue
   - AuthNav.vue

2. **Stores** (Critical - 90% target)
   - auth.js
   - State management
   - API calls

3. **Utils** (Medium - 85% target)
   - Date formatting
   - Validation helpers
   - CSRF utilities

## Quality Metrics

### Success Criteria
- ✅ 100% of tests passing
- ✅ 60%+ overall coverage
- ✅ 80%+ critical path coverage
- ✅ Zero flaky tests
- ✅ Tests run < 2 minutes
- ✅ Pre-commit hooks enabled
- ✅ Coverage badges visible

### Tracking
```
# Coverage Baseline (to be measured)
Backend:  ___%
Frontend: ___%
Overall:  ___%

# Target (End of Initiative)
Backend:  60%+
Frontend: 60%+
Overall:  60%+
```

## Testing Best Practices

### General Principles
1. ✅ Test behavior, not implementation
2. ✅ Write descriptive test names
3. ✅ Use fixtures for common setup
4. ✅ Mock external dependencies
5. ✅ Test both success and failure cases
6. ✅ Keep tests fast and isolated

### Backend Testing
```python
# Good test name
def test_user_login_with_valid_credentials_returns_jwt_token():
    # Arrange
    user_data = {"email": "test@example.com", "password": "password123"}  # pragma: allowlist secret

    # Act
    response = client.post("/api/auth/login", json=user_data)

    # Assert
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Frontend Testing
```javascript
// Good component test
describe('LoginForm.vue', () => {
  it('should show error message when login fails', async () => {
    // Arrange
    const wrapper = mount(LoginForm)

    // Act
    await wrapper.find('form').trigger('submit')

    // Assert
    expect(wrapper.find('.error-message').exists()).toBe(true)
  })
})
```

## Common Test Patterns

### Backend: Testing Protected Endpoints
```python
def test_protected_endpoint_requires_authentication():
    response = client.get("/api/admin/users")
    assert response.status_code == 401

def test_protected_endpoint_with_valid_token():
    token = get_admin_token()
    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

### Frontend: Testing User Interactions
```javascript
it('should submit form when button is clicked', async () => {
  const wrapper = mount(GameForm)

  // Fill form
  await wrapper.find('#home-team').setValue('Team A')
  await wrapper.find('#away-team').setValue('Team B')

  // Submit
  await wrapper.find('button[type="submit"]').trigger('click')

  // Verify
  expect(wrapper.emitted('game-submitted')).toBeTruthy()
})
```

## Tools & Resources

### Testing Tools
- **pytest** - Python testing framework
- **pytest-cov** - Coverage for Python
- **Jest** - JavaScript testing framework
- **Vue Test Utils** - Vue component testing
- **Schemathesis** - API contract testing
- **Playwright** - E2E testing (future)

### CI/CD Integration
```yaml
# .github/workflows/tests.yml (to be created)
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run backend tests
        run: cd backend && uv run pytest --cov

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run frontend tests
        run: cd frontend && npm test -- --coverage
```

## Monitoring & Maintenance

### Daily
- Check test status before commits
- Run tests locally before pushing
- Fix failing tests immediately

### Weekly
- Review test coverage trends
- Identify and remove flaky tests
- Update test documentation

### Monthly
- Review testing strategy
- Update coverage targets
- Optimize slow tests

## Known Issues & Workarounds

### Backend
- [ ] Schemathesis tests require running server (currently disabled)
- [ ] Some contract tests may need mock data

### Frontend
- [ ] Need to set up test environment configuration
- [ ] May need to mock Supabase client

## Success Metrics

### Week 1: Assessment Complete
- [ ] Baseline coverage documented
- [ ] All tests categorized
- [ ] Failing tests identified

### Week 4: Zero Failures Achieved
- [ ] All tests passing
- [ ] No flaky tests
- [ ] CI/CD runs green

### Week 8: Quality Gates Enabled
- [ ] 60%+ coverage achieved
- [ ] Pre-commit hooks working
- [ ] Coverage badges visible
- [ ] Documentation complete

## Resources

### Internal Docs
- [Testing Strategy](./TESTING_STRATEGY.md)
- [API Contract Testing](../backend/API_CONTRACT_TESTING.md)
- [Testing Guide](../backend/TESTING_GUIDE.md)

### External Resources
- [Pytest Documentation](https://docs.pytest.org/)
- [Jest Documentation](https://jestjs.io/)
- [Vue Test Utils](https://test-utils.vuejs.org/)

---

**Last Updated:** 2025-10-07
**Owner:** Development Team
**Status:** 🚀 In Progress - Phase 1: Assessment
