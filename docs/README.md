# 📚 Missing Table Documentation Hub

Welcome to the Missing Table documentation! This guide will help you get started, understand the system, and contribute effectively.

## 🎯 Quick Navigation

### New Here? Start With These:
1. **[🚀 Getting Started](01-getting-started/)** - Install and run the project in < 10 minutes
2. **[🎓 Contributing Guide](10-contributing/)** - Your first contribution (great for students!)
3. **[🏗️ Architecture Overview](03-architecture/)** - Understand how everything works

### By Role:

#### 👨‍💻 **Developers**
- [Development Workflow](02-development/) - Daily commands and best practices
- [Backend Guide](03-architecture/backend-structure.md) - FastAPI, DAO patterns, database
- [Frontend Guide](03-architecture/frontend-structure.md) - Vue.js, components, state
- [API Development](02-development/api-development.md) - Building new endpoints

#### 🧪 **QA / Testers**
- [Testing Strategy](04-testing/) - Test types, running tests, coverage
- [Quality Metrics](04-testing/quality-metrics.md) - Coverage goals, quality gates
- [API Testing](08-integrations/bruno-testing.md) - Bruno API test collections

#### 🚀 **DevOps / Infrastructure**
- [Deployment Guide](05-deployment/) - Docker, Kubernetes, GKE
- [Infrastructure Security](06-security/infrastructure-security.md) - Security scanning, policies
- [CI/CD Pipeline](09-cicd/) - GitHub Actions, quality gates
- [Operations](07-operations/) - Monitoring, backups, incidents

#### 🔐 **Security**
- [Security Overview](06-security/) - Authentication, secrets, scanning
- [Secret Management](06-security/secret-management.md) - How we handle secrets
- [Security Fixes](06-security/security-fixes.md) - Recent security improvements

---

## 📖 Documentation Map

### [01 - Getting Started](01-getting-started/)
> Everything you need to get the project running locally

- **[Installation](01-getting-started/installation.md)** - Prerequisites and setup
- **[Quick Start](01-getting-started/README.md)** - Run the app in 5 minutes
- **[Local Development](01-getting-started/local-development.md)** - Full local setup
- **[First Contribution](01-getting-started/first-contribution.md)** 🎓 Perfect for beginners!
- **[Troubleshooting](01-getting-started/troubleshooting.md)** - Common issues and fixes

### [02 - Development](02-development/)
> Daily workflows, commands, and development practices

- **[Daily Workflow](02-development/daily-workflow.md)** - Common commands and patterns
- **[Environment Management](02-development/environment-management.md)** - Local, dev, prod environments
- **[Database Operations](02-development/database-operations.md)** - Backup, restore, migrations
- **[Docker Guide](02-development/docker-guide.md)** - Building images, platform considerations
- **[API Development](02-development/api-development.md)** - Creating new endpoints

### [03 - Architecture](03-architecture/)
> System design, patterns, and technical decisions

- **[System Design](03-architecture/README.md)** - High-level architecture overview
- **[Backend Structure](03-architecture/backend-structure.md)** - FastAPI, DAO, database
- **[Frontend Structure](03-architecture/frontend-structure.md)** - Vue.js, components, routing
- **[Authentication](03-architecture/authentication.md)** - Auth flow, JWT, roles
- **[Database Schema](03-architecture/database-schema.md)** - Tables, relationships
- **[AI Agents](03-architecture/ai-agents.md)** - Autonomous agent architecture

### [04 - Testing](04-testing/)
> Testing strategy, coverage, and quality metrics

- **[Testing Strategy](04-testing/testing-strategy.md)** - Overall approach and goals
- **[Backend Testing](04-testing/backend-testing.md)** - Pytest, fixtures, coverage
- **[Frontend Testing](04-testing/frontend-testing.md)** - Jest, Vue Test Utils
- **[API Contract Testing](04-testing/api-contract-testing.md)** - Schemathesis tests
- **[Quality Metrics](04-testing/quality-metrics.md)** - Coverage goals, quality gates
- **[Test Results](04-testing/test-results/)** - Historical test reports

### [05 - Deployment](05-deployment/)
> Docker, Kubernetes, GKE, and infrastructure management

- **[Deployment Overview](05-deployment/README.md)** - Deployment options
- **[Docker Guide](02-development/docker-guide.md)** - Docker image building
- **[Kubernetes](05-deployment/kubernetes.md)** - K8s concepts and usage
- **[GKE Deployment](05-deployment/gke-deployment.md)** - Google Kubernetes Engine
- **[Helm Charts](05-deployment/helm-charts.md)** - Helm deployment configuration
- **[HTTPS Setup](05-deployment/https-setup.md)** - SSL certificates, custom domains
- **[Infrastructure](05-deployment/infrastructure/)** - Terraform, ArgoCD, GitOps

### [06 - Security](06-security/)
> Authentication, secrets, vulnerability scanning, and security best practices

- **[Security Guide](06-security/security-guide.md)** - Comprehensive security overview
- **[Secret Management](06-security/secret-management.md)** - Storing and protecting secrets
- **[Secret Runtime Loading](06-security/secret-runtime.md)** - How secrets are loaded
- **[Infrastructure Security](06-security/infrastructure-security.md)** - Container and K8s security
- **[Security Fixes](06-security/security-fixes.md)** - Recent security improvements

### [07 - Operations](07-operations/)
> Running the system, monitoring, backups, and troubleshooting

- **[Database Backup](07-operations/database-backup.md)** - Backup and restore procedures
- **[Monitoring](07-operations/monitoring.md)** - Health checks, metrics, logging
- **[Uptime Testing](07-operations/uptime-testing.md)** - Automated health verification
- **[Incident Response](07-operations/incident-response.md)** - When things go wrong

### [08 - Integrations](08-integrations/)
> External integrations and API usage

- **[Match Scraper](08-integrations/match-scraper.md)** - MLS Next data scraper integration
- **[API Usage](08-integrations/api-usage.md)** - Using the Missing Table API
- **[Bruno Testing](08-integrations/bruno-testing.md)** - API testing with Bruno

### [09 - CI/CD](09-cicd/)
> Continuous integration and deployment pipelines

- **[Pipeline Overview](09-cicd/pipeline.md)** - CI/CD architecture
- **[GitHub Actions](09-cicd/github-actions.md)** - Workflow configurations
- **[Quality Gates](09-cicd/quality-gates.md)** - Automated quality enforcement
- **[Testkube Integration](09-cicd/testkube-integration.md)** - E2E testing automation
- **[Testkube GKE CI/CD Plan](TESTKUBE_GKE_CICD_PLAN.md)** ⭐ Implementation guide

### [10 - Contributing](10-contributing/)
> How to contribute to the project

- **[Contributing Guide](10-contributing/README.md)** - Start here!
- **[For Students](10-contributing/for-students.md)** 🎓 Perfect for learners
- **[Code Style](10-contributing/code-style.md)** - Coding standards
- **[Pull Request Guide](10-contributing/pull-request-guide.md)** - PR process
- **[Learning Resources](10-contributing/learning-resources.md)** - External tutorials

---

## 🎓 Learning Paths

### Path 1: Frontend Developer
1. [Getting Started](01-getting-started/) → [Frontend Structure](03-architecture/frontend-structure.md) → [Frontend Testing](04-testing/frontend-testing.md)

### Path 2: Backend Developer
1. [Getting Started](01-getting-started/) → [Backend Structure](03-architecture/backend-structure.md) → [API Development](02-development/api-development.md) → [Backend Testing](04-testing/backend-testing.md)

### Path 3: Full Stack Developer
1. [Getting Started](01-getting-started/) → [System Design](03-architecture/) → [Development Workflow](02-development/) → [Testing](04-testing/)

### Path 4: DevOps Engineer
1. [Docker Guide](02-development/docker-guide.md) → [Kubernetes](05-deployment/kubernetes.md) → [GKE Deployment](05-deployment/gke-deployment.md) → [CI/CD](09-cicd/)

### Path 5: First-Time Contributor (Student)
1. [For Students](10-contributing/for-students.md) → [First Contribution](01-getting-started/first-contribution.md) → [Code Style](10-contributing/code-style.md) → [Pull Request Guide](10-contributing/pull-request-guide.md)

---

## 🔍 Quick Reference

### Most Common Commands
```bash
# Start development environment
./missing-table.sh dev

# Run tests
cd backend && uv run pytest
cd frontend && npm test

# Database operations
./scripts/db_tools.sh backup
./scripts/db_tools.sh restore

# Build for cloud deployment
./build-and-push.sh all dev
```

### Key Files
- **[CLAUDE.md](../CLAUDE.md)** - AI assistant guide (references this documentation)
- **[README.md](../README.md)** - Project overview and quick start
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - How to contribute

---

## 🆘 Need Help?

### Can't Find What You're Looking For?
1. Use the search function (Cmd/Ctrl + F) in this page
2. Check the [Troubleshooting Guide](01-getting-started/troubleshooting.md)
3. Search existing [GitHub Issues](https://github.com/silverbeer/missing-table/issues)
4. Ask a question in [Discussions](https://github.com/silverbeer/missing-table/discussions)

### Documentation Issues?
Found a typo, broken link, or outdated information?
- [Open an issue](https://github.com/silverbeer/missing-table/issues/new?labels=documentation)
- [Submit a PR](../CONTRIBUTING.md) with the fix

---

## 📝 Documentation Standards

This documentation follows consistent formatting standards to ensure clarity and ease of use.

**See**: [Documentation Standards](../DOCUMENTATION_STANDARDS.md)

---

**Last Updated**: 2025-10-08
**Maintained by**: Missing Table Team
**License**: MIT

---

<div align="center">

Made with ❤️ by the Missing Table community

[⬆ Back to Top](#-missing-table-documentation-hub)

</div>
