# Test Baseline Report

**Date:** 2025-10-07
**Branch:** `feature/zero-failed-tests`
**Initiative:** Quality Initiative - Zero Failed Tests

## Executive Summary

This report establishes the baseline state of testing for the Missing Table project as of October 7, 2025. The assessment phase identified 191 backend tests and documented infrastructure improvements needed to achieve zero failed tests.

### Key Findings
- ✅ **191 tests discovered** in backend
- ⚠️ **Most tests require running server** to execute
- ✅ **Test infrastructure improved** (pytest markers registered, test files organized)
- ⚠️ **Frontend tests not yet assessed**
- ⚠️ **Coverage baseline not yet established**

---

## Backend Test Assessment

### Test Discovery

**Total Tests Collected:** 191

**Test Distribution:**
```
tests/contract/          # API contract tests
├── test_auth_contract.py       (3 tests)
├── test_games_contract.py      (3 tests)
├── test_invites_contract.py    (5 tests)
└── test_schemathesis.py        (1 test - skipped)

tests/                   # Core tests
├── test_api_endpoints.py
├── test_auth_endpoints.py
├── test_audit_trail.py
├── test_cli.py
├── test_dao.py
├── test_enhanced_e2e.py
├── test_invite_debug.py        (5 tests)
├── test_invite_e2e.py
└── test_supabase_connection.py
```

### Test Execution Status

**Unable to run most tests** because they require a running backend server:

```
! _pytest.outcomes.Exit: Backend server not running. Start server and try again. !
```

**Tests Skipped:** 1
- `tests/contract/test_schemathesis.py::test_api_schema_validation` - Requires running server

**Tests That Can Run Standalone:** Unknown (requires further investigation)

### Test Infrastructure Improvements

#### 1. Fixed Test File Organization
**Issue:** `test_minimal_app.py` in root directory was being collected as a test file
**Action:** Renamed to `minimal_app.py` (it's actually a minimal FastAPI app for testing, not a test file)
**Result:** Reduced false positive test from 192 to 191 actual tests

**Issue:** `test_audit_trail.py` in backend directory
**Action:** Moved to `tests/test_audit_trail.py` for better organization
**Result:** All tests now in proper tests/ directory structure

#### 2. Pytest Configuration Consolidated
**Issue:** Conflicting configuration between `pytest.ini` and `pyproject.toml`
**Action:** Removed `pytest.ini` (pyproject.toml takes precedence anyway)
**Result:** Single source of truth for pytest configuration

#### 3. Registered Custom Markers
**Issue:** 16 "Unknown pytest.mark" warnings for `debug` marker
**Action:** Added to pyproject.toml markers list
**Result:** Zero marker warnings

**Registered Markers:**
```toml
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"")",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "e2e: marks tests as end-to-end tests",
    "contract: marks tests as API contract tests",
    "debug: marks tests for debugging specific issues",
]
```

### Test Warnings

**Deprecation Warnings from Dependencies:**
```
- supabase/__init__.py: gotrue package deprecated → use supabase_auth instead
- supabase/__init__.py: supafunc package deprecated → use supabase_functions instead
```

**Note:** These are library warnings, not project code issues. Consider updating dependencies when stable alternatives are available.

---

## Frontend Test Assessment

### Status
**Not yet assessed** - Requires separate investigation

### Planned Actions
1. Navigate to `frontend/` directory
2. Run `npm test` to discover available tests
3. Run `npm run test:coverage` to generate coverage baseline
4. Document test structure and results
5. Identify any failing tests

---

## Test Infrastructure

### Current Test Stack

**Backend:**
- **Framework:** pytest 8.4.2
- **Coverage:** pytest-cov with .coveragerc configuration
- **Async Support:** pytest-asyncio with auto mode
- **Contract Testing:** Schemathesis 4.2.0 (currently disabled)
- **Additional Plugins:**
  - pytest-respx 0.22.0
  - pytest-xdist 3.8.0
  - pytest-hypothesis 6.140.3
  - pytest-anyio 4.10.0
  - pytest-typeguard 4.4.4
  - pytest-logfire 4.4.0
  - pytest-subtests 0.14.2

**Frontend:**
- **Framework:** Jest (assumed - to be verified)
- **Vue Testing:** Vue Test Utils (assumed - to be verified)
- **Status:** Not yet assessed

### Test Execution Requirements

#### Server-Dependent Tests (Majority)
Most tests require a running backend server at `http://localhost:8000`:

**Required Setup:**
```bash
# Start backend server
cd backend && uv run python app.py

# OR use the service management script
./missing-table.sh dev  # Auto-reload mode (recommended)
```

**Test Categories Requiring Server:**
- API endpoint tests
- Authentication tests
- Contract tests
- E2E tests
- Integration tests

#### Standalone Tests (Minority)
Tests that can run without server (exact count unknown):
- Unit tests (possibly)
- Some DAO tests (possibly)
- Mock-based tests (possibly)

**Action Required:** Categorize tests by dependency type to optimize test running

---

## Coverage Baseline

### Status
**Not yet established** - Requires running tests with server

### Planned Measurement
```bash
# Backend coverage
cd backend && uv run pytest --cov=. --cov-report=html --cov-report=term

# Frontend coverage
cd frontend && npm run test:coverage
```

### Expected Deliverables
- Coverage percentage by module
- Critical path coverage analysis
- Identification of untested code
- Gap analysis for missing tests

---

## Test Quality Metrics

### Current State
- ✅ **Test Discovery:** 191 tests found
- ✅ **Test Organization:** All tests in proper directories
- ✅ **Configuration:** Consolidated to pyproject.toml
- ✅ **Markers:** All custom markers registered
- ⚠️ **Test Execution:** Cannot run without server
- ❌ **Coverage Baseline:** Not yet established
- ❌ **Pass/Fail Status:** Unknown (server required)
- ❌ **Flaky Tests:** Unknown
- ❌ **Test Speed:** Unknown

### Blockers
1. **Server Dependency:** Most tests require running backend server
2. **Environment Setup:** Database must be configured (Supabase local or cloud)
3. **Test Data:** Unknown if tests need specific data fixtures

---

## Next Steps

### Phase 1 Continuation: Complete Assessment

#### Immediate Tasks (This Week)
1. ✅ Audit current test status → **COMPLETED**
2. 🔄 **IN PROGRESS:** Document test baseline findings
3. ⏳ Set up local test environment with running server
4. ⏳ Run all backend tests and document results
5. ⏳ Run all frontend tests and document results
6. ⏳ Generate initial coverage reports
7. ⏳ Identify and categorize failing tests

#### Environment Setup Required
```bash
# 1. Start local Supabase (if not already running)
npx supabase start

# 2. Restore database from backup
./scripts/db_tools.sh restore

# 3. Start backend server in dev mode
./missing-table.sh dev

# 4. Run tests in separate terminal
cd backend && uv run pytest -v --tb=short
```

#### Documentation Tasks
- [ ] Create test execution guide
- [ ] Document test data requirements
- [ ] List all test dependencies
- [ ] Create troubleshooting guide for common test failures

### Phase 2 Preview: Fix & Stabilize

Once assessment is complete:
1. Fix all failing tests
2. Separate unit tests from integration tests
3. Create fast test suite (tests that don't need server)
4. Set up test database fixtures
5. Achieve zero failed tests

---

## Test Execution Guide (Draft)

### Running Backend Tests

#### Prerequisites
1. Backend server running at http://localhost:8000
2. Local Supabase running (or cloud environment configured)
3. Database populated with test data

#### Test Commands
```bash
# Run all tests
cd backend && uv run pytest

# Run with verbose output
cd backend && uv run pytest -v

# Run specific test file
cd backend && uv run pytest tests/test_auth_endpoints.py

# Run with coverage
cd backend && uv run pytest --cov=. --cov-report=html --cov-report=term

# Run tests by marker
cd backend && uv run pytest -m "unit"              # Unit tests only
cd backend && uv run pytest -m "not slow"          # Exclude slow tests
cd backend && uv run pytest -m "integration"       # Integration tests only
cd backend && uv run pytest -m "contract"          # Contract tests only
cd backend && uv run pytest -m "debug"             # Debug tests only

# Stop on first failure
cd backend && uv run pytest -x

# Show test durations
cd backend && uv run pytest --durations=10
```

### Running Frontend Tests

**Status:** Commands to be documented after frontend assessment

---

## Known Issues

### Critical
1. **Server Dependency:** Cannot run most tests without backend server running
2. **Coverage Unknown:** Need baseline metrics before proceeding

### Medium
3. **Test Organization:** Need to separate unit tests from integration tests for faster feedback
4. **Test Data:** Unknown test data requirements and fixtures needed
5. **Schemathesis Tests:** Currently disabled - need to enable contract testing

### Low
6. **Dependency Warnings:** Supabase dependencies deprecated (gotrue, supafunc)
7. **Test Speed:** Unknown - need to measure and optimize

---

## Recommendations

### Short Term (Week 1)
1. ✅ Complete this baseline report
2. Set up automated test environment (script to start server + run tests)
3. Run full test suite and capture results
4. Generate coverage reports
5. Document all failing tests with root causes

### Medium Term (Week 2-3)
1. Fix all failing tests
2. Separate fast unit tests from slow integration tests
3. Create test data fixtures for reliable test execution
4. Enable Schemathesis contract tests
5. Achieve zero failed tests

### Long Term (Week 4+)
1. Improve coverage to 60%+ (stepping stone to 80%)
2. Set up pre-commit hooks for testing
3. Create GitHub Actions quality gates
4. Add coverage badges to README
5. Document testing best practices

---

## Files Modified During Assessment

### Configuration Changes
- ❌ **Removed:** `backend/pytest.ini` (redundant with pyproject.toml)
- ✏️ **Modified:** `backend/pyproject.toml` (added debug marker)

### File Organization
- 📁 **Moved:** `test_audit_trail.py` → `tests/test_audit_trail.py`
- ✏️ **Renamed:** `test_minimal_app.py` → `minimal_app.py` (not a test file)
- ✏️ **Modified:** `minimal_app.py:109` (updated uvicorn reference)

### Summary of Changes
- Improved test file organization
- Consolidated pytest configuration
- Eliminated pytest marker warnings
- Reduced false positives in test collection

---

## Appendix A: Raw Test Output

### Test Collection (Clean)
```
$ uv run pytest --collect-only -q

2 empty files skipped.
Coverage HTML written to dir htmlcov
=========================== short test summary info ============================
SKIPPED [1] tests/contract/test_schemathesis.py:18: Schemathesis tests require running server - skipping for initial setup
191 tests collected, 1 skipped in 0.13s
```

### Test Execution Attempt (Without Server)
```
$ uv run pytest -v --tb=short -x

======================= 1 skipped, 18 warnings in 0.28s ========================
! _pytest.outcomes.Exit: Backend server not running. Start server and try again. !
```

---

## Appendix B: Test File Inventory

### Contract Tests (`tests/contract/`)
- `test_auth_contract.py` - Authentication contract validation
- `test_games_contract.py` - Games API contract validation
- `test_invites_contract.py` - Invites API contract validation
- `test_schemathesis.py` - OpenAPI schema validation (disabled)

### Core Tests (`tests/`)
- `test_api_endpoints.py` - API endpoint functionality
- `test_auth_endpoints.py` - Authentication endpoints
- `test_audit_trail.py` - Audit logging functionality
- `test_cli.py` - Command-line interface
- `test_dao.py` - Data Access Object layer
- `test_enhanced_e2e.py` - End-to-end workflows
- `test_invite_debug.py` - Invite system debugging
- `test_invite_e2e.py` - Invite end-to-end workflows
- `test_supabase_connection.py` - Database connectivity

---

## Conclusion

The test assessment phase has successfully:
1. ✅ Discovered 191 backend tests
2. ✅ Cleaned up test infrastructure and configuration
3. ✅ Eliminated pytest configuration conflicts
4. ✅ Registered all custom markers
5. ✅ Organized test files properly

**Next Critical Step:** Set up test execution environment with running server to complete the assessment and establish coverage baseline.

The foundation is now solid for Phase 2 (Fix & Stabilize) once we complete the remaining assessment tasks.

---

**Report Status:** 📝 Draft - Assessment In Progress
**Next Update:** After running full test suite with server
