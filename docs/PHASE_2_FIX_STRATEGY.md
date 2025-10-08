# Phase 2: Fix Strategy - Zero Failed Tests

**Goal:** Fix all 27 failing tests to achieve ZERO failures
**Current Status:** 158 passing, 27 failing, 7 skipped

---

## Failure Analysis Summary

### 1. Invite E2E Tests - 13 Failures ❌ (HIGHEST PRIORITY)

**Root Cause:** Authentication mocking not working with FastAPI dependencies

**Problem:**
Tests are using `patch('api.invites.get_current_user_required')` but FastAPI uses `Depends()` which caches the dependency. The mock doesn't override the actual dependency injection.

**Error Pattern:**
```
assert response.status_code == 200
assert 403 == 200  # Getting Forbidden instead of success
```

**Files Affected:**
- `tests/test_invite_e2e.py` - All 13 tests in this file

**Solution:**
Use FastAPI's `app.dependency_overrides` mechanism:

```python
# Instead of:
with patch('api.invites.get_current_user_required', return_value=admin_user_mock):
    response = test_client.post(...)

# Use:
from app import app  # Import the FastAPI app
from auth import get_current_user_required

def override_get_current_user():
    return admin_user_mock

app.dependency_overrides[get_current_user_required] = override_get_current_user
try:
    response = test_client.post(...)
finally:
    app.dependency_overrides.clear()
```

**Estimated Time:** 1-2 hours
**Priority:** 🔴 CRITICAL - Most failures, core functionality

---

### 2. DAO Tests - 6 Failures ❌

**Root Cause:** DAO interface mismatch - tests expect old API

**Error Pattern:**
```
AttributeError: 'EnhancedSportsDataAccess' object has no attribute 'X'
```

**Files Affected:**
- `tests/test_dao.py` - 6 tests

**Likely Issues:**
1. Method names changed during refactoring
2. Return value structure changed
3. Tests using old DAO interface

**Solution:**
1. Review actual DAO methods in `dao/enhanced_data_access_fixed.py`
2. Update test expectations to match current implementation
3. Verify return value structures match

**Estimated Time:** 1 hour
**Priority:** 🟡 HIGH - Data layer is critical

---

### 3. Auth Contract Tests - 5 Failures ❌

**Root Cause:** API response structure mismatch

**Error Pattern:**
Tests expecting certain response fields that may not exist or have different names.

**Files Affected:**
- `tests/contract/test_auth_contract.py` - 5 tests
  - test_signup_success
  - test_logout
  - test_get_profile_authenticated
  - test_get_profile_unauthenticated
  - test_refresh_token

**Solution:**
1. Run each test individually to see exact assertion failures
2. Compare expected response structure vs actual
3. Update test assertions to match current API contract
4. May need to update API client in `api_client/client.py`

**Estimated Time:** 1-1.5 hours
**Priority:** 🟡 HIGH - Authentication is critical

---

### 4. Invites Contract Tests - 2 Failures ❌

**Root Cause:** Similar to #1 - endpoint or response structure issues

**Files Affected:**
- `tests/contract/test_invites_contract.py` - 2 tests
  - test_invite_endpoints_exist
  - test_cancel_invite_requires_invite_id

**Solution:**
1. Verify endpoints exist and are registered
2. Check response structures match expected contract
3. May overlap with #1 fix (dependency overrides)

**Estimated Time:** 30 minutes
**Priority:** 🟢 MEDIUM

---

### 5. API Endpoints Test - 1 Failure ❌

**Root Cause:** Unauthorized access test expectation

**Files Affected:**
- `tests/test_api_endpoints.py::TestUnauthorizedEndpoints::test_create_game_unauthorized`

**Likely Issue:**
Test expects 401 Unauthorized but may be getting 403 Forbidden or different status code.

**Solution:**
Check actual status code returned and update assertion.

**Estimated Time:** 15 minutes
**Priority:** 🟢 LOW - Single test

---

## Fix Order Strategy

### Phase 2a: Quick Wins (30-45 minutes)
1. ✅ Fix API endpoint unauthorized test (#5) - 15 min
2. ✅ Fix invite contract tests (#4) - 30 min

### Phase 2b: Core Fixes (2-3 hours)
3. ✅ Fix Invite E2E tests (#1) - 1-2 hours (CRITICAL)
4. ✅ Fix DAO tests (#2) - 1 hour
5. ✅ Fix Auth contract tests (#3) - 1-1.5 hours

### Phase 2c: Verification (30 minutes)
6. ✅ Run full test suite
7. ✅ Verify ZERO failures
8. ✅ Update pyramid visualization
9. ✅ Document fixes

---

## Common Patterns to Watch For

### Pattern 1: FastAPI Dependency Injection
**Problem:** `patch()` doesn't work with `Depends()`
**Solution:** Use `app.dependency_overrides`

### Pattern 2: Response Structure Changes
**Problem:** Tests expect old API response format
**Solution:** Update test expectations to match current API

### Pattern 3: Method Rename/Refactoring
**Problem:** Tests call methods that no longer exist
**Solution:** Update test code to use current method names

### Pattern 4: Status Code Expectations
**Problem:** Tests expect 401 but API returns 403 (or vice versa)
**Solution:** Update assertions to match actual behavior

---

## Testing Commands

```bash
# Run all failing tests
uv run pytest tests/test_invite_e2e.py tests/test_dao.py tests/contract/test_auth_contract.py -v

# Run specific failure category
uv run pytest tests/test_invite_e2e.py -v
uv run pytest tests/test_dao.py -v
uv run pytest tests/contract/test_auth_contract.py -v

# Run single test for debugging
uv run pytest tests/test_invite_e2e.py::TestInviteWorkflowE2E::test_admin_create_team_manager_invite -vv

# Run and see pyramid after fixes
python pyramid_visualizer.py
```

---

## Success Criteria

- [ ] All 27 failing tests fixed
- [ ] 191 tests passing
- [ ] 0 tests failing
- [ ] Pyramid shows 100% pass rate at all levels
- [ ] No new test failures introduced
- [ ] Test execution time < 30 seconds

---

## Next Steps After Phase 2

Once we hit zero failures:
1. **Tag remaining tests** with proper markers
2. **Add missing tests** for uncovered code
3. **Improve coverage** from 16% → 60%
4. **Set up frontend testing** (Vitest + Vue Test Utils)
5. **Add pre-commit hooks** for automated testing
6. **CI/CD integration** with quality gates

---

**Document Status:** Active Fix Strategy
**Last Updated:** 2025-10-07
**Target Completion:** Today!
