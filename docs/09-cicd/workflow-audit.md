# 🔍 GitHub Actions Workflow Audit

> **Date**: 2025-10-08
> **Branch**: workflow-audit
> **Purpose**: Complete audit of all GitHub Actions workflows to ensure they pass when run and are useful/needed

---

## 📊 Executive Summary

**Total Workflows**: 9
**Passing**: 1 (11%)
**Failing**: 8 (89%)
**Status**: 🚨 **CRITICAL** - Most workflows are failing

### Key Findings

1. **Most workflows are failing** - 8 out of 9 workflows have recent failures
2. **Several workflows are not properly configured** - YAML parsing errors
3. **Some workflows may be redundant** - Multiple security scanning workflows
4. **Missing dependencies** - Scripts referenced in workflows may not exist
5. **Configuration issues** - Some workflows reference non-existent paths/files

---

## 📋 Workflow Inventory

### 1. ✅ CI/CD Pipeline with Quality Gates
**File**: `.github/workflows/ci-cd-pipeline.yml`
**Status**: ❌ **FAILING** (Invalid YAML - workflow file not found)
**Triggers**:
- Push to `main`, `develop`, `v1.*`
- Pull requests to `main`, `develop`
- Manual workflow dispatch

**Purpose**: Comprehensive multi-stage CI/CD pipeline with:
- Code quality checks (Ruff, MyPy, ESLint, Biome)
- Security scanning (Bandit, Safety, NPM audit, Trivy)
- Testing (unit, integration, coverage)
- Container security
- Infrastructure security
- Quality gate validation
- Deployment to GKE
- Performance validation
- Notifications

**Issues**:
- ❌ GitHub Actions reports "workflow file not found" error
- ❌ YAML may have parsing issues
- ❌ Very complex (848 lines) - difficult to maintain
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v3`)
- ⚠️ Aggressive quality thresholds (90% test coverage, 0 vulnerabilities)
- ⚠️ Missing required secrets for deployment

**Recommendation**:
- **FIX** - Validate YAML syntax
- **SIMPLIFY** - Break into smaller, focused workflows
- **DOCUMENT** - Add inline comments explaining each stage
- **UPDATE** - Use v4 of upload-artifact action

---

### 2. 🚀 GCP Deployment with Security Scanning
**File**: `.github/workflows/gcp-deploy.yml`
**Status**: ❌ **FAILING**
**Triggers**:
- Push to `main`, `develop` (when backend/frontend/gcp changed)
- Pull requests to `main` (when backend/frontend/gcp changed)
- Manual workflow dispatch

**Purpose**: Deploy to Google Cloud Platform with:
- Security scanning (Trivy, Hadolint)
- Terraform planning and validation
- Docker image building and pushing to GAR
- Deployment to staging/production GKE
- Binary authorization attestation
- Image cleanup

**Issues**:
- ❌ Missing GCP configuration (no `gcp/` directory found)
- ❌ Missing secrets (`WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`)
- ❌ References non-existent files (`gcp/k8s/staging/*.yaml`)
- ⚠️ Terraform plan job will always fail (missing terraform files)
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v3`)

**Recommendation**:
- **DISABLE** - Project doesn't use GCP for deployment (uses local GKE via Rancher)
- **DOCUMENT** - Keep as reference for future GCP migration
- **ARCHIVE** - Move to `.github/workflows/archive/` directory

---

### 3. 🔐 Infrastructure Security Scanning
**File**: `.github/workflows/infrastructure-security.yml`
**Status**: ❌ **FAILING** (scheduled runs fail)
**Triggers**:
- Push to `main`, `develop` (when terraform/k8s/workflow changed)
- Pull requests to `main` (when terraform/k8s changed)
- Daily schedule (3 AM UTC)
- Manual dispatch

**Purpose**: Scan infrastructure code with:
- Terraform security (Checkov, Terrascan, TFSec, Trivy)
- Kubernetes security (Trivy, Polaris, KubeLinter, Datree)
- Docker security (Trivy, Hadolint)
- Consolidated reporting

**Issues**:
- ❌ No `terraform/` directory in project root
- ❌ Missing Polaris config (`k8s/polaris/polaris-config.yaml`)
- ❌ Missing Falco config (`k8s/falco/falco-config.yaml`)
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v4` in some places, `v3` in others)
- ⚠️ Datree requires secret `DATREE_TOKEN`
- ⚠️ Scans multiple Dockerfiles (regular + secure versions)

**Recommendation**:
- **FIX** - Update paths to match actual project structure (`helm/` not `terraform/`)
- **SIMPLIFY** - Remove checks for files that don't exist
- **UPDATE** - Consistent artifact action versions
- **CONFIGURE** - Add Polaris/Datree configs or remove those steps

---

### 4. ⚡ Performance Budget Validation
**File**: `.github/workflows/performance-budget.yml`
**Status**: ❌ **FAILING** (scheduled runs fail)
**Triggers**:
- Daily schedule (6 AM UTC)
- Manual dispatch with environment selection

**Purpose**: Validate performance against budgets:
- Lighthouse CI testing (desktop + mobile)
- Performance budget validation
- Load testing with K6
- Slack notifications

**Issues**:
- ❌ Missing secrets (`APP_URL_STAGING`, `APP_URL_PRODUCTION`)
- ❌ No actual JSON parsing in validation step (placeholders only)
- ❌ Load testing requires staging/production URLs
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v3`)
- ⚠️ K6 test script embedded in workflow (should be external file)

**Recommendation**:
- **CONFIGURE** - Add staging/production URL secrets
- **ENHANCE** - Implement actual Lighthouse report parsing
- **EXTRACT** - Move K6 script to `backend/tests/performance/load-test.js`
- **UPDATE** - Use v4 of upload-artifact action
- **KEEP** - Valuable for production monitoring

---

### 5. ⚙️ Quality Gates Configuration
**File**: `.github/workflows/quality-gates-config.yml`
**Status**: ❌ **FAILING** (Invalid YAML - workflow file not found)
**Triggers**: None (configuration file, not a workflow)

**Purpose**: YAML configuration file defining quality thresholds

**Issues**:
- ❌ GitHub Actions trying to run this as a workflow
- ❌ This is NOT a workflow - it's a configuration file
- ❌ Should not be in `.github/workflows/` directory

**Recommendation**:
- **MOVE** - Relocate to `.github/quality-gates-config.yml` or `config/`
- **DOCUMENT** - Add README explaining its purpose
- **REFERENCE** - Update other workflows to reference new location

---

### 6. 📅 Scheduled Security Scan
**File**: `.github/workflows/security-scan-scheduled.yml`
**Status**: ❌ **FAILING** (Invalid YAML - workflow file not found)
**Triggers**:
- Daily schedule (2 AM UTC)
- Weekly comprehensive scan (Sunday 2 AM UTC)
- Manual dispatch with scan type selection

**Purpose**: Comprehensive scheduled security scanning:
- Dependency scanning (Safety, pip-audit, npm audit, retire.js)
- Code security (Bandit, Semgrep, ESLint)
- Secrets scanning (TruffleHog, GitLeaks)
- Infrastructure security
- Container security
- Report generation

**Issues**:
- ❌ GitHub Actions reports "workflow file not found" error
- ❌ YAML parsing errors likely
- ❌ Missing bandit config (`bandit.yaml`)
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v3`)
- ⚠️ Very comprehensive (528 lines) - may overlap with other workflows
- ⚠️ TruffleHog command syntax may be incorrect

**Recommendation**:
- **FIX** - Validate YAML syntax
- **DEDUPLICATE** - Consolidate with `security-scan.yml`
- **UPDATE** - Use v4 of upload-artifact action
- **CONFIGURE** - Add missing bandit.yaml config

---

### 7. 🔒 Secret Detection
**File**: `.github/workflows/secret-detection.yml`
**Status**: ❌ **FAILING** (detect-secrets baseline audit fails)
**Triggers**:
- Push to `main`, `develop`, `feature/*`, `hotfix/*`
- Pull requests to `main`, `develop`
- Manual dispatch

**Purpose**: Detect secrets in code with:
- GitLeaks scanning
- detect-secrets scanning
- Baseline audit
- Summary reporting

**Issues**:
- ❌ Baseline audit failing (unaudited secrets in `.secrets.baseline`)
- ⚠️ May be detecting false positives
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v4` but inconsistent)

**Recommendation**:
- **FIX** - Audit `.secrets.baseline` to mark false positives
- **KEEP** - This is critical for security
- **UPDATE** - Consistent artifact action version
- **DOCUMENT** - Add instructions for handling false positives

---

### 8. 🛡️ Security Scanning
**File**: `.github/workflows/security-scan.yml`
**Status**: ✅ **PASSING** (most recent run successful)
**Triggers**:
- Push to `main`, `develop`
- Pull requests to `main`
- Daily schedule (2 AM UTC)
- Manual dispatch

**Purpose**: Regular security scanning:
- Trivy scans (backend/frontend images, filesystem, config)
- Secret scanning with Trivy
- Dependency scanning (npm audit, Python safety)

**Issues**:
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v4`)
- ⚠️ Builds Docker images without caching
- ⚠️ Overlaps with `security-scan-scheduled.yml`

**Recommendation**:
- **KEEP** - This is the working security workflow
- **CONSOLIDATE** - Merge with `security-scan-scheduled.yml`
- **OPTIMIZE** - Add Docker build caching
- **UPDATE** - Keep this as primary security workflow

---

### 9. 📝 API Contract Tests
**File**: `.github/workflows/api-contract-tests.yml`
**Status**: ❌ **FAILING**
**Triggers**:
- Push to `main`, `develop`, `feature/**` (when backend changed)
- Pull requests to `main`, `develop` (when backend changed)

**Purpose**: Validate API contracts with:
- OpenAPI schema export and validation
- Contract tests (pytest)
- API coverage checking
- Schemathesis property-based tests
- PR comments with coverage report

**Issues**:
- ❌ Missing scripts (`backend/scripts/export_openapi.py`)
- ❌ Missing scripts (`backend/scripts/check_api_coverage.py`)
- ❌ Missing test directory (`backend/tests/contract/`)
- ❌ Missing Schemathesis test file
- ⚠️ Uses deprecated actions (`actions/upload-artifact@v4`)

**Recommendation**:
- **CREATE** - Implement missing scripts and tests
- **DOCUMENT** - Add guide for API contract testing
- **KEEP** - Valuable for API quality assurance
- **FIX** - Once scripts are created, this workflow is useful

---

## 🎯 Action Plan

### Phase 1: Immediate Fixes (High Priority)

1. **Fix YAML Parsing Errors** ⚠️
   - [ ] Validate all YAML files with `yamllint`
   - [ ] Fix `ci-cd-pipeline.yml` parsing errors
   - [ ] Fix `security-scan-scheduled.yml` parsing errors
   - [ ] Fix `quality-gates-config.yml` (move out of workflows/)

2. **Fix Secret Detection** 🔒
   - [ ] Audit `.secrets.baseline` and mark false positives
   - [ ] Run `detect-secrets audit .secrets.baseline`
   - [ ] Update baseline with `detect-secrets scan --update .secrets.baseline`

3. **Fix API Contract Tests** 📝
   - [ ] Create `backend/scripts/export_openapi.py`
   - [ ] Create `backend/scripts/check_api_coverage.py`
   - [ ] Create `backend/tests/contract/` directory
   - [ ] Add placeholder contract tests

### Phase 2: Consolidation (Medium Priority)

4. **Consolidate Security Workflows** 🛡️
   - [ ] Keep `security-scan.yml` as primary
   - [ ] Merge useful parts from `security-scan-scheduled.yml`
   - [ ] Remove redundant scans
   - [ ] Add comprehensive scheduling

5. **Archive Unused Workflows** 📦
   - [ ] Move `gcp-deploy.yml` to archive (not using GCP)
   - [ ] Move `quality-gates-config.yml` to `config/` directory
   - [ ] Document archived workflows

### Phase 3: Enhancement (Low Priority)

6. **Improve Infrastructure Security** 🏗️
   - [ ] Update paths to match project structure (helm/ not terraform/)
   - [ ] Add missing config files (Polaris, Datree)
   - [ ] Remove checks for non-existent directories

7. **Configure Performance Testing** ⚡
   - [ ] Add staging/production URL secrets
   - [ ] Implement Lighthouse report parsing
   - [ ] Extract K6 scripts to separate files

8. **Simplify CI/CD Pipeline** 🔄
   - [ ] Break large workflow into smaller focused workflows
   - [ ] Add inline documentation
   - [ ] Update deprecated actions

### Phase 4: Documentation (Ongoing)

9. **Create Workflow Documentation** 📚
   - [ ] Document each workflow's purpose
   - [ ] Add troubleshooting guides
   - [ ] Create workflow dependency diagram
   - [ ] Add examples for manual workflow dispatch

10. **Update Project Documentation** 📖
    - [ ] Update `docs/09-cicd/README.md` with workflow info
    - [ ] Add workflow status badges to main README
    - [ ] Create workflow maintenance guide

---

## 📊 Workflow Comparison Matrix

| Workflow | Status | Complexity | Useful | Priority | Action |
|----------|--------|------------|--------|----------|--------|
| ci-cd-pipeline.yml | ❌ | Very High | Yes | High | Fix & Simplify |
| gcp-deploy.yml | ❌ | High | No | Low | Archive |
| infrastructure-security.yml | ❌ | High | Yes | Medium | Fix Paths |
| performance-budget.yml | ❌ | Medium | Yes | Medium | Configure |
| quality-gates-config.yml | ❌ | N/A | Yes | High | Move File |
| security-scan-scheduled.yml | ❌ | Very High | Yes | High | Fix & Merge |
| secret-detection.yml | ❌ | Low | Yes | High | Fix Baseline |
| security-scan.yml | ✅ | Medium | Yes | High | Keep & Enhance |
| api-contract-tests.yml | ❌ | Medium | Yes | High | Create Scripts |

---

## 🔧 Quick Fixes

### Fix 1: Move quality-gates-config.yml

```bash
# This is not a workflow - it's a configuration file
mkdir -p .github/config
git mv .github/workflows/quality-gates-config.yml .github/config/quality-gates-config.yml
```

### Fix 2: Archive GCP deployment workflow

```bash
# Not using GCP - archive for future reference
mkdir -p .github/workflows/archive
git mv .github/workflows/gcp-deploy.yml .github/workflows/archive/
```

### Fix 3: Fix secret detection baseline

```bash
# Audit and update the baseline
cd /path/to/repo
detect-secrets audit .secrets.baseline
detect-secrets scan --update .secrets.baseline
```

### Fix 4: Validate all workflow YAML

```bash
# Install yamllint
brew install yamllint  # or: pip install yamllint

# Check all workflows
yamllint .github/workflows/*.yml
```

---

## 📈 Success Metrics

**Goals**:
- ✅ **All enabled workflows pass** when they run
- ✅ **No redundant workflows** - each serves unique purpose
- ✅ **All workflows documented** - purpose and usage clear
- ✅ **Fast feedback** - critical checks complete in < 10 minutes
- ✅ **Actionable results** - failures provide clear next steps

**Target State**:
- 6-7 workflows (down from 9)
- 80%+ passing rate (up from 11%)
- < 5 minutes average runtime for critical workflows
- 100% of workflows have documentation

---

## 🔗 Related Documentation

- **[CI/CD Pipeline Guide](pipeline.md)** - Detailed CI/CD documentation
- **[Security Guide](../06-security/security-guide.md)** - Security practices
- **[Testing Strategy](../04-testing/testing-strategy.md)** - Testing approach
- **[Deployment Guide](../05-deployment/)** - Deployment procedures

---

<div align="center">

**Audit Status**: 🚨 In Progress
**Next Update**: After Phase 1 completion

[⬆ Back to CI/CD Documentation](README.md) | [⬆ Back to Documentation Hub](../README.md)

</div>
