# Archived Workflows

This directory contains GitHub Actions workflows that are no longer actively used but are kept for reference.

## Archived Workflows

### api-contract-tests.yml
**Date Archived**: 2025-10-08
**Reason**: Not ready for contract/integration/e2e tests yet - only unit tests for now
**Status**: Workflow functional but testing infrastructure not ready
**Future Use**: Reactivate when dev environment is set up for contract, component, integration, and e2e CI testing

**What it does**:
- Exports OpenAPI schema from FastAPI app
- Validates schema against OpenAPI spec
- Runs pytest contract tests
- Runs Schemathesis property-based tests
- Checks API coverage and comments on PRs

**Why archived**:
- Project currently only runs unit tests
- Contract tests would run against dev Supabase (not ready yet)
- Need to set up proper test environment first
- Integration/e2e testing infrastructure not configured

**To reactivate**:
1. Set up dev environment for testing (test database, test data)
2. Configure test environment variables
3. Ensure backend scripts work (`export_openapi.py`, `check_api_coverage.py`)
4. Add comprehensive contract tests in `backend/tests/contract/`
5. Move workflow back to `.github/workflows/`
6. Update workflow to use test environment, not production

---

### gcp-deploy.yml
**Date Archived**: 2025-10-08
**Reason**: Project currently uses local Rancher/GKE deployment, not Google Cloud Platform
**Status**: Complete but unused
**Future Use**: Can be reactivated if project migrates to GCP in the future

**What it does**:
- Builds and pushes Docker images to Google Artifact Registry
- Deploys to staging/production GKE clusters on GCP
- Runs security scanning (Trivy, Hadolint)
- Performs Terraform validation and deployment
- Creates Binary Authorization attestations

**Why archived**:
- The project currently deploys to a local Kubernetes cluster via Rancher
- Uses Helm charts in `helm/missing-table/` instead of raw Kubernetes manifests
- No GCP project configured
- Missing required secrets (`WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`)
- References non-existent `gcp/` directory

**To reactivate**:
1. Set up GCP project and configure Workload Identity Federation
2. Add required secrets to GitHub repository
3. Create `gcp/` directory structure with Terraform and Kubernetes manifests
4. Move workflow back to `.github/workflows/`
5. Update paths and configurations

---

### ci-cd-pipeline.yml
**Date Archived**: 2025-10-08 (Phase 2)
**Reason**: Complex workflow with YAML parsing errors and many unmet dependencies
**Status**: Needs significant refactoring
**Future Use**: Can be rebuilt as smaller, focused workflows when needed

**What it does**:
- Comprehensive multi-stage CI/CD pipeline
- Code quality checks (Ruff, MyPy, ESLint, Biome, TypeScript)
- Security scanning (Bandit, Safety, NPM audit, Trivy, Grype)
- Unit and integration testing with coverage
- Container security scanning
- Infrastructure security validation
- Quality gate enforcement
- Deployment to GKE
- Performance validation
- Slack notifications

**Why archived**:
- GitHub Actions reports "workflow file not found" (YAML parsing errors)
- Very complex (848 lines) - difficult to maintain and debug
- Aggressive quality thresholds (90% coverage, 0 vulnerabilities)
- Missing required secrets for deployment (GCP keys)
- Overlaps significantly with security-scan.yml
- Too comprehensive for current project needs

**To reactivate**:
1. Fix YAML syntax errors
2. Break into smaller, focused workflows (quality, security, deploy)
3. Adjust quality thresholds to realistic levels
4. Configure required secrets
5. Test each component independently
6. Consider using simpler workflows until project scales

---

### security-scan-scheduled.yml
**Date Archived**: 2025-10-08 (Phase 2)
**Reason**: YAML parsing errors and redundant with security-scan.yml
**Status**: Redundant - security-scan.yml provides same functionality
**Future Use**: Features can be merged into security-scan.yml if needed

**What it does**:
- Daily and weekly comprehensive security scans
- Dependency scanning (Safety, pip-audit, npm audit, retire.js)
- Code security (Bandit, Semgrep, ESLint)
- Secrets scanning (TruffleHog, GitLeaks)
- Infrastructure and container security
- Consolidated security reports

**Why archived**:
- GitHub Actions reports "workflow file not found" (YAML parsing errors)
- Very comprehensive but overlaps heavily with security-scan.yml
- security-scan.yml already runs on push/PR and daily schedule
- 528 lines - complex and difficult to maintain
- Some tool configurations may be incorrect

**To reactivate**:
1. Fix YAML syntax errors
2. OR merge unique features into security-scan.yml
3. Ensure no overlap with existing security workflows
4. Test all security tools work correctly

---

### infrastructure-security.yml
**Date Archived**: 2025-10-08 (Phase 2)
**Reason**: References non-existent directories (terraform/, k8s/ structure)
**Status**: Needs path updates to match project structure
**Future Use**: Reactivate after updating paths to helm/ directory

**What it does**:
- Terraform security scanning (Checkov, Terrascan, TFSec, Trivy)
- Kubernetes security scanning (Trivy, Polaris, KubeLinter, Datree)
- Docker security scanning (Trivy, Hadolint)
- Consolidated infrastructure security reporting

**Why archived**:
- References `terraform/` directory that doesn't exist
- References `k8s/` directory structure that doesn't match project
- Project uses `helm/` for Kubernetes deployments
- Missing config files (Polaris, Falco, Datree)
- Would fail on every run due to path mismatches

**To reactivate**:
1. Update paths from `terraform/` to `helm/`
2. Update k8s scanning to scan `helm/missing-table/templates/`
3. Add or remove tools based on actual needs
4. Add missing config files or remove those checks
5. Test against actual project structure

---

### performance-budget.yml
**Date Archived**: 2025-10-08 (Phase 2)
**Reason**: Missing required secrets (staging/production URLs) and not critical for current development
**Status**: Functional but not configured
**Future Use**: Reactivate when have staging/production environments set up

**What it does**:
- Daily Lighthouse CI testing (desktop + mobile)
- Core Web Vitals validation
- Performance budget enforcement
- Load testing with K6
- Slack notifications on performance issues

**Why archived**:
- Missing secrets: `APP_URL_STAGING`, `APP_URL_PRODUCTION` # pragma: allowlist secret
- No staging or production environments currently deployed
- Scheduled daily but can't run without URLs
- Load testing needs actual deployment to test
- Not critical for current local development focus

**To reactivate**:
1. Deploy to staging/production environments
2. Add `APP_URL_STAGING` and `APP_URL_PRODUCTION` secrets
3. Implement actual Lighthouse report parsing (currently placeholders)
4. Extract K6 scripts to separate files
5. Test against actual deployments

---

### secret-detection.yml
**Date Archived**: 2025-10-08 (Phase 2)
**Reason**: Baseline audit failing and redundant with security-scan.yml
**Status**: Functional but requires interactive baseline audit
**Future Use**: Can reactivate after auditing `.secrets.baseline` or use security-scan.yml instead

**What it does**:
- GitLeaks secret scanning on every push/PR
- detect-secrets baseline scanning
- Baseline audit to catch new unaudited secrets
- Summary reporting

**Why archived**:
- Baseline audit failing (unaudited secrets in `.secrets.baseline`)
- Requires interactive `detect-secrets audit` to mark false positives
- security-scan.yml already includes Trivy secret scanning
- Pre-commit hook already runs detect-secrets locally
- Redundant with existing secret detection layers

**To reactivate**:
1. Run `detect-secrets audit .secrets.baseline` interactively
2. Mark all false positives (test keys, examples, etc.)
3. Run `detect-secrets scan --update .secrets.baseline`
4. Move workflow back to `.github/workflows/`
5. OR simply rely on security-scan.yml + pre-commit hook

---

**Note**: Before reactivating any archived workflow, ensure all dependencies are in place and test thoroughly.
