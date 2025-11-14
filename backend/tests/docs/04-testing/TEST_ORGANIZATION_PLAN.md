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

See `test-migration-mapping.csv` for complete file-by-file mapping.

---

## 🧹 Cleanup Actions

### Immediate Actions (P1 - DELETE FIRST)

1. **Delete backup files**
   ```bash
   rm backend/tests/test_version.backup_*.py
   ```

2. **Delete debug test**
   ```bash
   rm backend/tests/test_invite_debug.py
   ```

3. **Delete duplicate/superseded tests**
   ```bash
   rm backend/tests/test_version.py  # Duplicate
   rm backend/tests/test_club_filtering_bug.py  # Superseded
   rm backend/tests/test_crew_generated_club_filtering.py  # Early experiment
   ```

4. **Archive legacy script**
   ```bash
   mkdir -p .archive/tests/
   mv backend/tests/legacy_e2e_supabase_script.py .archive/tests/
   ```

**Files to DELETE:** 6 files (saves ~27KB)
**Files to KEEP:** 15 files
**Files to REFACTOR:** 8 files

---

## 📅 Implementation Plan

### Phase 1: Cleanup (1 day)
- [ ] Delete all backup files (3 files)
- [ ] Delete debug/superseded tests (3 files)
- [ ] Archive legacy scripts (1 file)
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

## ✅ Success Criteria

### Definition of Done

- [ ] All backup files deleted (3 files)
- [ ] All debug/legacy tests removed or archived (4 files)
- [ ] New directory structure created and populated
- [ ] All tests passing in new locations
- [ ] Coverage thresholds met for each layer
- [ ] CI/CD pipelines updated
- [ ] Documentation updated

---

**Last Updated:** 2025-11-11  
**Next Review:** After Phase 1 completion
