# Testing & Quality Strategy

## Current Status

✅ **Repository Cleaned** (as of 2025-10-07)
- All failed workflow runs deleted
- Clean slate for quality initiatives
- Focus: Zero test failures, high code coverage

## Goals

### Primary Goals
1. **Zero Failed Tests** - All tests must pass on every commit
2. **High Code Coverage** - Target: 80%+ coverage across codebase
3. **Clean CI/CD** - No failed workflow runs in repository

### Quality Metrics Tracking
- Backend test coverage: Target 80%+
- Frontend test coverage: Target 80%+
- API contract tests: 100% endpoint coverage
- Security scans: Zero critical/high vulnerabilities

## Current Test Infrastructure

### Backend Testing
**Location:** `backend/tests/`
**Framework:** pytest
**Coverage:** pytest-cov

```bash
# Run backend tests
cd backend && uv run pytest

# Run with coverage
cd backend && uv run pytest --cov=. --cov-report=html --cov-report=term

# View coverage report
open backend/htmlcov/index.html
```

**Test Types:**
- Unit tests: Individual function/class tests
- Integration tests: Database and API integration
- E2E tests: Full user workflow tests
- Contract tests: API endpoint validation

### Frontend Testing
**Location:** `frontend/tests/`
**Framework:** Jest + Vue Test Utils
**Coverage:** Built into Jest

```bash
# Run frontend tests
cd frontend && npm test

# Run with coverage
cd frontend && npm run test:coverage

# Watch mode for development
cd frontend && npm run test:watch
```

**Test Types:**
- Component tests: Vue component behavior
- Store tests: Vuex/Pinia state management
- Integration tests: Component interactions
- E2E tests: (Planned with Playwright)

### API Contract Testing
**Location:** `.github/workflows/api-contract-tests.yml`
**Framework:** Schemathesis
**Status:** ⚠️ Currently disabled (requires running server)

```bash
# Run contract tests manually (requires backend running)
cd backend && uv run schemathesis run http://localhost:8000/openapi.json
```

## Testing Workflow

### Pre-Commit
```bash
# Run locally before committing
./run-tests.sh  # (Create this script)

# Or manually:
cd backend && uv run pytest
cd frontend && npm test
```

### CI/CD Pipeline
1. **On PR Creation:**
   - Run all backend tests
   - Run all frontend tests
   - Run security scans
   - Check code coverage

2. **On Merge to Main:**
   - Full test suite
   - Deploy to dev environment
   - Run smoke tests
   - Update coverage reports

3. **Scheduled (Daily):**
   - Security vulnerability scans
   - Dependency updates check
   - Performance regression tests

## Coverage Targets

### Backend Coverage Goals
```
Overall:        80%+
Critical paths: 95%+
- Authentication: 95%
- Game management: 90%
- Standings calculation: 95%
- Admin operations: 85%
```

### Frontend Coverage Goals
```
Overall:        80%+
Components:     75%+
Stores:         90%+
Utils:          85%+
```

## Test Organization

### Backend Test Structure
```
backend/tests/
├── unit/              # Pure function tests
│   ├── test_auth.py
│   ├── test_games.py
│   └── test_standings.py
├── integration/       # Database/API tests
│   ├── test_api_auth.py
│   ├── test_api_games.py
│   └── test_database.py
├── e2e/              # Full workflow tests
│   └── test_user_workflows.py
└── conftest.py       # Pytest fixtures
```

### Frontend Test Structure
```
frontend/tests/
├── unit/
│   ├── components/    # Component tests
│   ├── stores/        # Store tests
│   └── utils/         # Utility tests
├── integration/       # Component integration
└── e2e/              # Playwright tests (planned)
```

## Quality Gates

### Required for PR Merge
- [ ] All tests passing
- [ ] No decrease in code coverage
- [ ] Security scans pass
- [ ] Code review approved
- [ ] No linting errors

### Blocked by Quality Gates
- Cannot merge if tests fail
- Cannot merge if coverage drops >2%
- Cannot merge if critical security issues found

## Improving Code Coverage

### Priority Areas
1. **Backend:**
   - Add tests for game CRUD operations
   - Test standings calculation edge cases
   - Test invite code validation
   - Test role-based access control

2. **Frontend:**
   - Test all Vue components
   - Test auth store thoroughly
   - Test form validation
   - Test error handling

### Coverage Reports
```bash
# Generate coverage badge
cd backend && uv run pytest --cov=. --cov-report=term --cov-report=html

# Upload to coverage service (optional)
# codecov, coveralls, or similar
```

## Testing Best Practices

### Backend Tests
1. Use fixtures for common setup
2. Test both success and failure cases
3. Mock external dependencies (Supabase)
4. Test edge cases and boundaries
5. Use descriptive test names

### Frontend Tests
1. Test user interactions, not implementation
2. Use data-testid for stable selectors
3. Test accessibility
4. Mock API calls
5. Test error states

## Monitoring & Alerts

### GitHub Actions
- Slack/email notifications for test failures
- Coverage reports on PRs
- Daily test summary reports

### Metrics Dashboard (Future)
- Test success rate over time
- Coverage trends
- Mean time to fix failures
- Flaky test tracking

## Current Workflows

### Active Workflows
- ✅ Security Scanning (secret detection, trivy)
- ✅ GCP Deployment
- ⚠️ API Contract Tests (disabled - needs server)
- ⚠️ Performance Budget (needs configuration)

### To Fix/Enable
1. **API Contract Tests:** Configure with test database
2. **Performance Budget:** Set realistic thresholds
3. **Infrastructure Security:** Review and fix issues
4. **Quality Gates:** Configure coverage requirements

## Resources

### Documentation
- [Pytest Documentation](https://docs.pytest.org/)
- [Jest Documentation](https://jestjs.io/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [Schemathesis](https://schemathesis.readthedocs.io/)

### Internal Docs
- [API Contract Testing Guide](./API_CONTRACT_TESTING.md)
- [E2E Testing Guide](./E2E_TESTING.md)
- [Docker Build Guide](./DOCKER_BUILD_GUIDE.md)

## Next Steps

### Immediate (This Week)
1. ✅ Clean up failed workflow runs
2. Create `run-tests.sh` script for local testing
3. Enable pre-commit hooks for tests
4. Document current coverage baseline

### Short Term (This Month)
1. Add tests to reach 60% backend coverage
2. Add tests to reach 60% frontend coverage
3. Fix and enable API contract tests
4. Set up coverage reporting in CI

### Long Term (Next Quarter)
1. Reach 80%+ coverage on both frontend and backend
2. Implement E2E testing with Playwright
3. Add performance regression testing
4. Set up coverage badges and dashboards

## Maintenance

### Weekly
- Review test failures and fix immediately
- Check coverage trends
- Review and remove flaky tests

### Monthly
- Update dependencies
- Review and optimize slow tests
- Update test documentation

### Quarterly
- Review testing strategy
- Evaluate new testing tools
- Update coverage targets

---

**Last Updated:** 2025-10-07
**Owner:** Development Team
**Status:** ✅ Clean slate - ready to build quality infrastructure
