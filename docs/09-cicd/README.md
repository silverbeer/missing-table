# ⚙️ CI/CD Documentation

> **Audience**: DevOps engineers, developers
> **Platform**: GitHub Actions
> **Pipeline Duration**: < 30 minutes

Documentation for continuous integration and deployment pipelines.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Pipeline Overview](pipeline.md)** | Complete CI/CD architecture |
| **[GitHub Actions](github-actions.md)** | Workflow configurations |
| **[Quality Gates](quality-gates.md)** | Automated quality enforcement |

---

## 🎯 Pipeline Overview

### Stages

```
1. Code Quality    → Linting, formatting
2. Security Scan   → Secrets, vulnerabilities
3. Testing         → Unit, integration, E2E
4. Build           → Docker images
5. Deploy          → Dev/Prod environments
6. Verify          → Health checks, smoke tests
```

---

## 🚦 Quality Gates

### Required to Pass

- ✅ Zero linting errors
- ✅ All tests pass
- ✅ No critical/high vulnerabilities
- ✅ Code coverage ≥ 80%
- ✅ Security scans pass

### Workflow

**On Pull Request**:
- Run tests
- Check coverage
- Security scan
- Build verification

**On Merge to Main**:
- Full test suite
- Build & push images
- Deploy to dev
- Run smoke tests

---

## 🔧 GitHub Actions Workflows

### Active Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **CI** | PR, Push | Run tests, lint, build |
| **Security Scan** | Daily | Vulnerability scanning |
| **Deploy Dev** | Merge to main | Deploy to dev environment |
| **Deploy Prod** | Tag release | Deploy to production |

### Workflow Files

```
.github/workflows/
├── ci.yml                    # Main CI pipeline
├── security-scan.yml         # Daily security scans
├── deploy-dev.yml           # Dev deployment
└── deploy-prod.yml          # Prod deployment
```

---

## 📊 Pipeline Metrics

### Performance Targets

- **Pipeline Duration**: < 30 minutes
- **Success Rate**: > 95%
- **Mean Time to Recovery**: < 15 minutes
- **Deployment Frequency**: Multiple per day

---

## 📖 Related Documentation

- **[Testing](../04-testing/)** - Test strategy
- **[Deployment](../05-deployment/)** - Deployment guides
- **[Security](../06-security/)** - Security practices

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
