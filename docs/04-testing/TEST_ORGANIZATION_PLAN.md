# Test Organization & Refactoring Plan

**Status:** 🚧 Draft for Review
**Author:** Claude Code
**Date:** 2025-11-11
**Branch:** `tests-cleanup-refactor`

---

## 📋 Table of Contents

1. [Target Test Organization Structure](#target-test-organization-structure)
2. [Coverage Thresholds](#coverage-thresholds)
3. [Current Test Inventory](#current-test-inventory)
4. [Migration Mapping](#migration-mapping)
5. [Cleanup Actions](#cleanup-actions)
6. [Implementation Plan](#implementation-plan)

---

## 🎯 Target Test Organization Structure

```
backend/tests/
├── unit/                           # Fast, isolated component tests
│   ├── dao/                        # Data access layer tests
│   ├── services/                   # Business logic service tests
│   ├── models/                     # Model validation tests
│   └── utils/                      # Utility function tests
│
├── integration/                    # Component interaction tests
│   ├── api/                        # API endpoint tests (with TestClient)
│   ├── database/                   # Database integration tests
│   └── auth/                       # Authentication flow tests
│
├── contract/                       # API contract tests (existing)
│   ├── test_auth_contract.py
│   ├── test_games_contract.py
│   └── test_schemathesis.py
│
├── e2e/                           # End-to-end user journey tests
│   ├── test_user_signup_flow.py
│   ├── test_match_management.py
│   └── test_admin_workflows.py
│
├── smoke/                         # Quick sanity checks for deployments
│   ├── test_health_checks.py
│   ├── test_critical_endpoints.py
│   └── test_database_connectivity.py
│
├── fixtures/                      # Shared test fixtures
│   ├── auth_fixtures.py
│   ├── data_fixtures.py
│   └── mock_fixtures.py
│
├── helpers/                       # Test utilities and helpers
│   ├── api_helpers.py
│   ├── db_helpers.py
│   └── assertion_helpers.py
│
└── resources/                     # Test data and resources
    ├── sample_data/
    ├── mock_responses/
    └── test_configs/
```

---

## 📊 Coverage Thresholds

### Per-Layer Coverage Targets

| Layer | Minimum Coverage | Target Coverage | Speed | Test Count Target |
|-------|-----------------|-----------------|-------|-------------------|
| **Unit** | 80% | 90% | <100ms/test | 200+ tests |
| **Integration** | 70% | 80% | <500ms/test | 100+ tests |
| **Contract** | 90% | 95% | <1s/test | 50+ tests |
| **E2E** | 50% | 60% | <5s/test | 20+ tests |
| **Smoke** | 100% | 100% | <2s/test | 10+ tests |

### Overall Project Coverage

- **Minimum:** 75% overall code coverage
- **Target:** 85% overall code coverage
- **Critical Paths:** 100% coverage (auth, payments, data integrity)

### Performance Benchmarks

- **Unit tests:** Full suite <10 seconds
- **Integration tests:** Full suite <2 minutes
- **Contract tests:** Full suite <2 minutes
- **E2E tests:** Full suite <5 minutes
- **Smoke tests:** Full suite <30 seconds

---

## 📦 Current Test Inventory

### Summary Statistics

- **Total test files:** 21 (excluding backups)
- **Total lines of test code:** ~145 KB
- **Backup files:** 3 (should be deleted)
- **Legacy files:** 1 (needs review)
- **Duplicate tests:** ~3-4 files

### Test Files by Size

| File | Size | Lines | Est. Tests |
|------|------|-------|------------|
| `test_enhanced_e2e.py` | 19K | ~500 | 15-20 |
| `test_auth_endpoints.py` | 15K | ~400 | 12-15 |
| `test_invite_e2e.py` | 15K | ~400 | 10-12 |
| `test_api_endpoints.py` | 13K | ~350 | 20-25 |
| `test_club_filtering_bug.py` | 11K | ~300 | 8-10 |
| `test_teams_api_league_filtering.py` | 8.3K | ~220 | 6-8 |
| `conftest.py` | 8.2K | ~220 | N/A (fixtures) |
| `test_invite_debug.py` | 7.8K | ~200 | 5-7 |
| `test_dao.py` | 6.4K | ~170 | 10-12 |
| `legacy_e2e_supabase_script.py` | 5.9K | ~150 | 5-8 |
| `test_clubs.py` | 5.8K | ~155 | 6-8 |

---

## 🗺️ Migration Mapping

### Unit Tests (Target: `backend/tests/unit/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `test_dao.py` | `unit/dao/test_data_access.py` | Backend | REFACTOR | P1 | Split into focused test modules |
| `test_clubs.py` | `unit/models/test_clubs.py` | Backend | MOVE | P2 | Review if truly unit tests |
| `test_matches.py` | `unit/models/test_matches.py` | Backend | MOVE | P2 | Review if truly unit tests |

### Integration Tests (Target: `backend/tests/integration/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `test_api_endpoints.py` | `integration/api/test_endpoints.py` | API Team | REFACTOR | P1 | Split by endpoint type |
| `test_auth_endpoints.py` | `integration/auth/test_auth_flows.py` | Auth Team | REFACTOR | P1 | Extract to unit + integration |
| `test_teams_api_league_filtering.py` | `integration/api/test_teams_filtering.py` | API Team | MOVE | P2 | Rename for clarity |
| `test_api_version.py` | `integration/api/test_version_endpoint.py` | API Team | MERGE | P3 | Merge with test_version.py |
| `test_version.py` | DELETE | N/A | DELETE | P3 | Duplicate of test_api_version.py |

### Contract Tests (Target: `backend/tests/contract/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `contract/test_auth_contract.py` | KEEP | Contract | KEEP | P1 | ✅ Already well-organized |
| `contract/test_games_contract.py` | KEEP | Contract | KEEP | P1 | ✅ Already well-organized |
| `contract/test_schemathesis.py` | KEEP | Contract | KEEP | P1 | ✅ Already well-organized |

### E2E Tests (Target: `backend/tests/e2e/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `test_enhanced_e2e.py` | `e2e/test_user_workflows.py` | QA Team | REFACTOR | P1 | Split into focused scenarios |
| `test_invite_e2e.py` | `e2e/test_invite_workflow.py` | Auth Team | REFACTOR | P2 | Clean up and document |
| `test_invite_debug.py` | DELETE | N/A | DELETE | P2 | Debug code shouldn't be committed |
| `legacy_e2e_supabase_script.py` | ARCHIVE | N/A | ARCHIVE | P3 | Move to .archive/ or delete |

### Smoke Tests (Target: `backend/tests/smoke/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| N/A | `smoke/test_health_checks.py` | DevOps | CREATE | P1 | Extract from test_api_endpoints.py |
| N/A | `smoke/test_database_connectivity.py` | DevOps | CREATE | P2 | Create new smoke tests |

### Bug-Specific Tests (Review Required)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `test_club_filtering_bug_ai.py` | `integration/api/test_clubs_filtering.py` | API Team | MERGE | P2 | Latest AI-generated test (✅ KEEP) |
| `test_club_filtering_bug.py` | DELETE | N/A | DELETE | P2 | Superseded by AI-generated version |
| `test_crew_generated_club_filtering.py` | DELETE | N/A | DELETE | P3 | Early AI experiment, superseded |

### Fixtures & Helpers (Target: `backend/tests/fixtures/` & `helpers/`)

| Current File | New Location | Owner | Action | Priority | Notes |
|--------------|--------------|-------|--------|----------|-------|
| `conftest.py` | `fixtures/conftest.py` + `helpers/` | All | REFACTOR | P1 | Extract shared fixtures |

### Backup Files (DELETE ALL)

| Current File | Action | Priority |
|--------------|--------|----------|
| `test_version.backup_20251110_140827.py` | DELETE | P1 |
| `test_version.backup_20251110_145600.py` | DELETE | P1 |
| `test_version.backup_20251110_151139.py` | DELETE | P1 |

---

## 🧹 Cleanup Actions

### Immediate Actions (P1)

1. **Delete backup files**
   ```bash
   rm backend/tests/test_version.backup_*.py
   ```

2. **Delete debug test**
   ```bash
   rm backend/tests/test_invite_debug.py
   ```

3. **Archive legacy script**
   ```bash
   mkdir -p .archive/tests/
   mv backend/tests/legacy_e2e_supabase_script.py .archive/tests/
   ```

4. **Delete duplicate/superseded tests**
   ```bash
   rm backend/tests/test_version.py  # Duplicate
   rm backend/tests/test_club_filtering_bug.py  # Superseded
   rm backend/tests/test_crew_generated_club_filtering.py  # Early experiment
   ```

### Refactoring Actions (P2)

1. **Create new directory structure**
2. **Split large test files** (test_enhanced_e2e.py, test_api_endpoints.py)
3. **Extract shared fixtures** from conftest.py
4. **Standardize test naming** conventions
5. **Add missing docstrings** to all test functions

### Documentation Actions (P3)

1. **Update README.md** with new structure
2. **Create testing guidelines** document
3. **Document coverage requirements** per layer
4. **Create test writing guide** with examples

---

## 📅 Implementation Plan

### Phase 1: Cleanup (1 day)
- [ ] Delete all backup files
- [ ] Delete debug/legacy tests
- [ ] Archive legacy scripts
- [ ] Create new directory structure

### Phase 2: Reorganization (2-3 days)
- [ ] Move contract tests (already organized)
- [ ] Create unit test structure
- [ ] Create integration test structure
- [ ] Move existing tests to new locations

### Phase 3: Refactoring (3-4 days)
- [ ] Split large test files
- [ ] Extract shared fixtures
- [ ] Standardize naming conventions
- [ ] Add documentation to tests

### Phase 4: New Tests (2-3 days)
- [ ] Create smoke test suite
- [ ] Fill coverage gaps
- [ ] Add missing unit tests
- [ ] Enhance integration tests

### Phase 5: Validation (1 day)
- [ ] Run full test suite
- [ ] Verify coverage metrics
- [ ] Update CI/CD pipelines
- [ ] Document new structure

---

## 📝 Owner Assignments

### Proposed Ownership

- **Unit Tests:** Backend team (primary developers)
- **Integration Tests:** API team + Backend team
- **Contract Tests:** QA team + API team
- **E2E Tests:** QA team
- **Smoke Tests:** DevOps team
- **Fixtures/Helpers:** Shared ownership (Backend team maintains)

### Review Requirements

- **P1 actions:** Require 1 reviewer approval
- **P2 actions:** Require 1 reviewer approval + QA sign-off
- **P3 actions:** Can be done independently with post-review

---

## ✅ Success Criteria

### Definition of Done

- [ ] All backup files deleted
- [ ] All debug/legacy tests removed or archived
- [ ] New directory structure created and populated
- [ ] All tests passing in new locations
- [ ] Coverage thresholds met for each layer
- [ ] CI/CD pipelines updated
- [ ] Documentation updated
- [ ] Team training completed

### Metrics to Track

- **Test count per layer**
- **Coverage per layer**
- **Test execution time per layer**
- **Flaky test percentage** (target: <2%)
- **Test maintenance effort** (time spent fixing tests)

---

## 🔗 Related Documents

- [Testing Strategy](./README.md)
- [pytest Best Practices](./pytest-best-practices.md)
- [Coverage Guidelines](./coverage-guidelines.md)
- [CI/CD Pipeline](../09-cicd/README.md)

---

**Last Updated:** 2025-11-11
**Next Review:** After Phase 1 completion
