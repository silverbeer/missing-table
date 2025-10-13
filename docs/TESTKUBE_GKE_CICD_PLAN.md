# Testkube GKE + CI/CD Implementation Plan

**Document Version:** 1.0
**Created:** 2025-10-13
**Status:** Planning Phase
**Target Branch:** `feature/testkube-gke-integration`

---

## 📋 Executive Summary

### Objective
Deploy Testkube to GKE and integrate with GitHub Actions to enable automated E2E testing for every feature branch deployment.

### Current State
- ✅ Backend E2E tests exist (`backend/tests/test_auth_endpoints.py`, `test_enhanced_e2e.py`)
- ✅ Tests run locally with pytest
- ✅ GKE cluster operational (`gke_missing-table_us-central1_missing-table-dev`)
- ✅ Testkube POC working on local K3s (Rancher Desktop)
- ❌ No automated testing in CI/CD pipeline
- ❌ Manual testing before merges
- ❌ No automated test execution on deployments

### Desired State
```
Feature Branch Push → GitHub Actions → Build Images → Deploy to GKE →
Trigger Testkube Tests → Report Results to PR → Block merge if failed
```

### Value Proposition
1. **Fast Feedback**: Detect issues within minutes of commit
2. **Quality Gates**: Prevent broken code from merging
3. **Confidence**: Deploy to production with automated validation
4. **Visibility**: Test results visible in PR comments
5. **Developer Experience**: No manual test execution needed

---

## 🎯 Goals and Non-Goals

### Goals
- ✅ Deploy Testkube to GKE `missing-table-dev` cluster
- ✅ Create test definitions for existing backend E2E tests
- ✅ Integrate GitHub Actions to trigger tests on PR/commit
- ✅ Post test results back to GitHub PRs
- ✅ Document the complete testing workflow
- ✅ Keep costs minimal (target: <$15/month additional)

### Non-Goals
- ❌ Frontend E2E tests (future work)
- ❌ Load/performance testing (separate initiative)
- ❌ Multi-cluster deployments (only dev cluster for now)
- ❌ Testkube Pro features (using OSS version)

---

## 🏗️ Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer Workflow                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │   Git Push to Feature      │
            │   Branch                   │
            └────────────┬───────────────┘
                         │
                         ▼
            ┌────────────────────────────┐
            │   GitHub Actions           │
            │   Workflow Triggered       │
            └────────────┬───────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐    ┌─────────┐    ┌──────────┐
    │ Build  │    │ Push to │    │  Deploy  │
    │ Images │───▶│ Registry│───▶│  to GKE  │
    └────────┘    └─────────┘    └────┬─────┘
                                       │
                                       ▼
                        ┌──────────────────────────┐
                        │ GKE Cluster              │
                        │ ┌──────────────────────┐ │
                        │ │  Backend Deployment  │ │
                        │ └──────────────────────┘ │
                        │ ┌──────────────────────┐ │
                        │ │  Testkube Engine     │ │
                        │ │  - API Server        │ │
                        │ │  - Test Executors    │ │
                        │ │  - MongoDB           │ │
                        │ └──────────────────────┘ │
                        └────────────┬─────────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │ Run E2E Tests          │
                        │ - Auth tests           │
                        │ - API tests            │
                        │ - Integration tests    │
                        └────────────┬───────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │ Report Results         │
                        │ - PR Comment           │
                        │ - GitHub Check         │
                        │ - Slack (optional)     │
                        └────────────────────────┘
```

### Component Breakdown

#### 1. Testkube on GKE
- **Namespace**: `testkube`
- **Components**:
  - Testkube API Server (1 pod)
  - MongoDB (1 pod, for test metadata)
  - Minio (1 pod, for artifacts)
  - NATS (1 pod, for messaging)
- **Resources**: ~1 GB RAM, ~0.5 CPU total
- **Storage**: 10 GB PV for MongoDB/Minio

#### 2. GitHub Actions Workflow
- **Trigger**: Push to feature branches, PRs
- **Steps**:
  1. Checkout code
  2. Build Docker images (backend/frontend)
  3. Push to Google Container Registry
  4. Deploy to GKE
  5. Wait for rollout
  6. Trigger Testkube tests
  7. Wait for test completion
  8. Post results to PR
  9. Fail if tests fail

#### 3. Test Definitions
- **Backend Auth Tests**: `test_auth_endpoints.py`
- **Backend API Tests**: `test_enhanced_e2e.py`
- **Format**: Kubernetes CRD (`Test` resource)
- **Execution**: Python 3.13 container with pytest

---

## 📅 Implementation Phases

### Phase 1: GKE Testkube Deployment (Est: 2 hours)

**Objective**: Get Testkube running on GKE

#### Steps:
1. **Switch to GKE context**
   ```bash
   kubectl config use-context gke_missing-table_us-central1_missing-table-dev
   ```

2. **Install Testkube via Helm**
   ```bash
   helm repo add kubeshop https://kubeshop.github.io/helm-charts
   helm repo update

   helm install testkube kubeshop/testkube \
     --namespace testkube \
     --create-namespace \
     --wait
   ```

3. **Verify Installation**
   ```bash
   kubectl get pods -n testkube
   kubectl get svc -n testkube
   ```

4. **Create Service Account for GitHub Actions**
   ```bash
   kubectl create serviceaccount testkube-github-actions -n testkube
   kubectl create clusterrolebinding testkube-github-actions \
     --clusterrole=cluster-admin \
     --serviceaccount=testkube:testkube-github-actions
   ```

#### Deliverables:
- ✅ Testkube pods running
- ✅ API server accessible within cluster
- ✅ Service account configured
- ✅ Helm values file saved in `helm/testkube/values-gke.yaml`

#### Validation:
```bash
# Port-forward and test API
kubectl port-forward -n testkube svc/testkube-api-server 8088:8088
curl http://localhost:8088/health
```

---

### Phase 2: Test Definition Creation (Est: 3 hours)

**Objective**: Define E2E tests as Testkube Test resources

#### Test 1: Backend Auth E2E

Create `k8s/testkube/backend-auth-e2e.yaml`:

```yaml
apiVersion: tests.testkube.io/v3
kind: Test
metadata:
  name: backend-auth-e2e
  namespace: testkube
  labels:
    app: missing-table
    test-type: e2e
    layer: backend
spec:
  type: pytest/test
  content:
    type: git
    repository:
      type: git
      uri: https://github.com/silverbeer/missing-table.git
      branch: main
      path: backend/tests
  executionRequest:
    args:
      - "test_auth_endpoints.py::TestAuthLogin"
      - "test_auth_endpoints.py::TestAuthSignup"
      - "-v"
      - "--tb=short"
      - "--junit-xml=results.xml"

    variables:
      TEST_MODE:
        name: TEST_MODE
        value: "true"
      SUPABASE_URL:
        name: SUPABASE_URL
        value: "https://ppgxasqgqbnauvxozmjw.supabase.co"
      BACKEND_URL:
        name: BACKEND_URL
        value: "http://missing-table-backend.missing-table-dev.svc.cluster.local:8000"

    secretEnvs:
      SUPABASE_SERVICE_KEY:
        secretName: testkube-secrets
        secretKey: supabase-service-key

    workingDir: backend

    # Python 3.13 image with uv
    image: ghcr.io/astral-sh/uv:python3.13-bookworm-slim

    preRunScript: |
      #!/bin/bash
      set -e
      echo "Installing dependencies..."
      uv pip install --system pytest pytest-cov httpx python-dotenv
      uv pip install --system -r requirements.txt || true
      echo "Dependencies installed"
```

#### Test 2: Backend API E2E

Create `k8s/testkube/backend-api-e2e.yaml`:

```yaml
apiVersion: tests.testkube.io/v3
kind: Test
metadata:
  name: backend-api-e2e
  namespace: testkube
  labels:
    app: missing-table
    test-type: e2e
spec:
  type: pytest/test
  content:
    type: git
    repository:
      type: git
      uri: https://github.com/silverbeer/missing-table.git
      branch: main
      path: backend/tests
  executionRequest:
    args:
      - "test_enhanced_e2e.py::TestCompleteGameLifecycle"
      - "-v"
      - "--tb=short"

    variables:
      TEST_MODE:
        name: TEST_MODE
        value: "true"
      SUPABASE_URL:
        name: SUPABASE_URL
        value: "https://ppgxasqgqbnauvxozmjw.supabase.co"
      BACKEND_URL:
        name: BACKEND_URL
        value: "http://missing-table-backend.missing-table-dev.svc.cluster.local:8000"

    secretEnvs:
      SUPABASE_SERVICE_KEY:
        secretName: testkube-secrets
        secretKey: supabase-service-key

    workingDir: backend
    image: ghcr.io/astral-sh/uv:python3.13-bookworm-slim

    preRunScript: |
      #!/bin/bash
      set -e
      uv pip install --system pytest httpx python-dotenv
      uv pip install --system -r requirements.txt || true
```

#### Create Secrets

Create `k8s/testkube/secrets.yaml` (NOT committed to git):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: testkube-secrets
  namespace: testkube
type: Opaque
stringData:
  supabase-service-key: "YOUR_SUPABASE_SERVICE_KEY_HERE"
```

#### Apply Test Definitions

```bash
# Create secret first
kubectl apply -f k8s/testkube/secrets.yaml

# Apply test definitions
kubectl apply -f k8s/testkube/backend-auth-e2e.yaml
kubectl apply -f k8s/testkube/backend-api-e2e.yaml

# Verify
kubectl get tests -n testkube
```

#### Manual Test Run (Validation)

```bash
# Install testkube CLI
brew install testkube

# Configure context
kubectl config use-context gke_missing-table_us-central1_missing-table-dev
kubectl port-forward -n testkube svc/testkube-api-server 8088:8088 &

# Run tests manually
testkube --api-uri http://localhost:8088 --client direct run test backend-auth-e2e -f
testkube --api-uri http://localhost:8088 --client direct run test backend-api-e2e -f
```

#### Deliverables:
- ✅ Test definition YAML files in `k8s/testkube/`
- ✅ Tests created in GKE Testkube
- ✅ Manual test execution successful
- ✅ Secret management documented

---

### Phase 3: GitHub Actions Integration (Est: 4 hours)

**Objective**: Automate test execution on every PR/commit

#### Create `.github/workflows/test-pr.yml`:

```yaml
name: Test Feature Branch

on:
  pull_request:
    branches: [main, dev]
  push:
    branches: [feature/*]

env:
  GCP_PROJECT_ID: missing-table
  GKE_CLUSTER: missing-table-dev
  GKE_ZONE: us-central1
  BACKEND_IMAGE: gcr.io/missing-table/backend
  FRONTEND_IMAGE: gcr.io/missing-table/frontend

jobs:
  build-and-test:
    name: Build, Deploy & Test
    runs-on: ubuntu-latest

    permissions:
      contents: read
      pull-requests: write
      checks: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for GCR
        run: gcloud auth configure-docker

      - name: Build Backend Image
        run: |
          ./build-and-push.sh backend dev

      - name: Build Frontend Image
        run: |
          ./build-and-push.sh frontend dev

      - name: Get GKE credentials
        run: |
          gcloud container clusters get-credentials $GKE_CLUSTER \
            --zone $GKE_ZONE \
            --project $GCP_PROJECT_ID

      - name: Deploy to GKE
        run: |
          kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
          kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
          kubectl rollout status deployment/missing-table-backend -n missing-table-dev --timeout=5m
          kubectl rollout status deployment/missing-table-frontend -n missing-table-dev --timeout=5m

      - name: Install Testkube CLI
        run: |
          curl -sSLf https://get.testkube.io | sh
          echo "$HOME/.testkube/bin" >> $GITHUB_PATH

      - name: Run Auth E2E Tests
        id: auth-tests
        run: |
          kubectl port-forward -n testkube svc/testkube-api-server 8088:8088 &
          sleep 3

          testkube --api-uri http://localhost:8088 --client direct \
            run test backend-auth-e2e \
            --watch \
            --execution-name "pr-${{ github.event.pull_request.number }}-auth-$(date +%s)"

      - name: Run API E2E Tests
        id: api-tests
        run: |
          testkube --api-uri http://localhost:8088 --client direct \
            run test backend-api-e2e \
            --watch \
            --execution-name "pr-${{ github.event.pull_request.number }}-api-$(date +%s)"

      - name: Comment PR with Results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const authStatus = '${{ steps.auth-tests.outcome }}' === 'success' ? '✅' : '❌';
            const apiStatus = '${{ steps.api-tests.outcome }}' === 'success' ? '✅' : '❌';

            const body = `## 🧪 E2E Test Results

            | Test Suite | Status |
            |------------|--------|
            | Backend Auth | ${authStatus} ${authStatus === '✅' ? 'Passed' : 'Failed'} |
            | Backend API | ${apiStatus} ${apiStatus === '✅' ? 'Passed' : 'Failed'} |

            **Deployment:** \`missing-table-dev\`
            **Branch:** \`${{ github.head_ref }}\`
            **Commit:** \`${{ github.sha }}\`

            <details>
            <summary>View Test Details</summary>

            - Auth Tests: [View Logs](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})
            - API Tests: [View Logs](https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }})

            </details>`;

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });

      - name: Fail if tests failed
        if: steps.auth-tests.outcome != 'success' || steps.api-tests.outcome != 'success'
        run: exit 1
```

#### Create `.github/workflows/README.md`:

```markdown
# GitHub Actions Workflows

## test-pr.yml

Automated E2E testing for feature branches.

**Trigger**: Push to feature/* branches or PR to main/dev
**Duration**: ~5-8 minutes
**What it does**:
1. Builds Docker images
2. Deploys to GKE dev environment
3. Runs E2E tests via Testkube
4. Comments results on PR
5. Blocks merge if tests fail

**Required Secrets**:
- `GCP_SA_KEY` - Google Cloud service account key

**Test Suites**:
- Backend Auth E2E: Login, signup, token validation
- Backend API E2E: Game lifecycle, data consistency
```

#### GitHub Repository Secrets

Add to GitHub repo settings → Secrets and variables → Actions:

```
GCP_SA_KEY = <base64-encoded service account JSON>
```

#### Branch Protection Rules

Configure in GitHub repo settings → Branches → main:
- ✅ Require status checks to pass before merging
- ✅ Status checks: "Build, Deploy & Test / build-and-test"
- ✅ Require branches to be up to date before merging

#### Deliverables:
- ✅ GitHub Actions workflow file
- ✅ Workflow documentation
- ✅ Secrets configured
- ✅ Branch protection enabled

---

### Phase 4: Documentation & Handoff (Est: 2 hours)

**Objective**: Document the complete system for team

#### Create Documentation

1. **`docs/09-cicd/testkube-integration.md`** - Complete guide
2. **`docs/04-testing/running-tests-cicd.md`** - Running tests in CI/CD
3. Update **`docs/README.md`** - Add CI/CD links
4. Update **`CLAUDE.md`** - Add testkube references

#### Documentation Topics:
- How to add new tests
- How to debug test failures
- How to run tests locally vs CI/CD
- Cost breakdown and monitoring
- Troubleshooting guide

#### Training/Handoff:
- Demo video (optional)
- Team walkthrough
- Q&A session

#### Deliverables:
- ✅ Complete documentation
- ✅ Updated README files
- ✅ Team trained

---

## 💰 Cost Analysis

### Infrastructure Costs

| Component | Resources | Monthly Cost |
|-----------|-----------|--------------|
| Testkube Pods (4) | 1 GB RAM, 0.5 CPU | ~$10 |
| Storage (10 GB PV) | SSD | ~$2 |
| Network Egress | Minimal | ~$1 |
| **Total** | | **~$13/month** |

### GitHub Actions Costs

- Free tier: 2,000 minutes/month
- Estimated usage: ~200 minutes/month (40 PRs × 5 min each)
- **Cost: $0** (within free tier)

### ROI Calculation

**Time Saved:**
- Manual testing per PR: 15 minutes
- PRs per month: 40
- Total time saved: 10 hours/month
- Developer cost @ $50/hr: **$500/month saved**

**ROI: ~3,800%** ($500 saved / $13 cost)

---

## 🚧 Risks & Mitigation

### Risk 1: Test Flakiness
**Impact**: False positives, lost confidence
**Probability**: Medium
**Mitigation**:
- Write deterministic tests
- Use proper wait strategies
- Implement retry logic for network calls
- Monitor test reliability metrics

### Risk 2: GKE Cluster Instability
**Impact**: Tests fail due to infrastructure
**Probability**: Low
**Mitigation**:
- Health checks before test execution
- Retry failed tests once
- Alert on infrastructure issues
- Separate test namespace

### Risk 3: Slow Test Execution
**Impact**: Slow PR feedback loop
**Probability**: Medium
**Mitigation**:
- Parallel test execution
- Optimize slow tests
- Consider test sharding
- Monitor execution time

### Risk 4: Secret Exposure
**Impact**: Security breach
**Probability**: Low
**Mitigation**:
- Use Kubernetes secrets
- Never commit secrets to git
- Rotate secrets regularly
- Use least-privilege service accounts

---

## 📊 Success Metrics

### Phase 1 (Deployment)
- ✅ Testkube pods healthy for 48 hours
- ✅ API server accessible
- ✅ Zero deployment errors

### Phase 2 (Test Definitions)
- ✅ 100% of existing E2E tests defined
- ✅ All tests pass manually
- ✅ Test execution time < 5 minutes

### Phase 3 (CI/CD Integration)
- ✅ GitHub Actions workflow triggers on PR
- ✅ Test results posted to PR
- ✅ Failed tests block merge
- ✅ Zero false positives in first week

### Phase 4 (Documentation)
- ✅ Team can add new tests independently
- ✅ < 5 minutes to understand system
- ✅ Zero documentation gaps

### Ongoing Success
- Test reliability > 99%
- Average test execution < 5 minutes
- Zero production bugs missed by tests
- Team satisfaction: "Would recommend"

---

## 🔄 Rollout Plan

### Week 1: Phase 1 (GKE Deployment)
- Day 1-2: Deploy Testkube to GKE
- Day 3: Validation and troubleshooting
- Day 4-5: Documentation

### Week 2: Phase 2 (Test Definitions)
- Day 1-2: Create test YAML files
- Day 3: Manual test execution
- Day 4-5: Refine and optimize

### Week 3: Phase 3 (GitHub Actions)
- Day 1-2: Create workflow file
- Day 3: Test on feature branch
- Day 4-5: Rollout to all branches

### Week 4: Phase 4 (Documentation)
- Day 1-3: Write comprehensive docs
- Day 4: Team training
- Day 5: Retrospective and improvements

---

## 🔮 Future Enhancements

### Phase 5: Frontend E2E Tests
- Playwright integration
- Visual regression testing
- Cross-browser testing

### Phase 6: Performance Testing
- Load testing with k6
- API performance benchmarks
- Database query optimization

### Phase 7: Multi-Environment
- Staging environment testing
- Production smoke tests
- Canary deployment validation

### Phase 8: Advanced Features
- Test result trends/analytics
- Slack notifications
- Auto-retry flaky tests
- Parallel test execution

---

## 📚 References

### External Documentation
- [Testkube Documentation](https://docs.testkube.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Pytest Documentation](https://docs.pytest.org/)

### Internal Documentation
- [Backend Testing Guide](../04-testing/backend-testing.md)
- [GKE Deployment Guide](../05-deployment/gke-deployment.md)
- [Secret Management](../06-security/secret-management.md)

### Related Issues/PRs
- TBD: Create tracking issue
- TBD: Link to implementation PR

---

## ✅ Checklist

### Pre-Implementation
- [ ] Review this plan with team
- [ ] Get approval from stakeholders
- [ ] Verify GKE cluster capacity
- [ ] Confirm budget approval
- [ ] Create feature branch

### During Implementation
- [ ] Phase 1 complete
- [ ] Phase 2 complete
- [ ] Phase 3 complete
- [ ] Phase 4 complete

### Post-Implementation
- [ ] Monitor for 1 week
- [ ] Gather team feedback
- [ ] Document lessons learned
- [ ] Plan future enhancements

---

## 👥 Team & Responsibilities

**Implementation Lead**: TBD
**DevOps Support**: TBD
**QA Review**: TBD
**Documentation**: TBD

---

## 🤝 Getting Help

**Questions about this plan?**
- Open a discussion in GitHub Discussions
- Ping @maintainer in Slack
- Review the [Testkube documentation](https://docs.testkube.io/)

**Found an issue?**
- Update this document
- Notify the team
- Create a tracking issue

---

**Last Updated**: 2025-10-13
**Next Review**: After Phase 1 completion
**Status**: Ready for Implementation

---

*This plan is a living document. Update it as you learn and adapt!*
