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

**Note**: Before reactivating any archived workflow, ensure all dependencies are in place and test thoroughly.
