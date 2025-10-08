# 🔐 Security Documentation

> **Audience**: Developers, security engineers, DevOps
> **Importance**: Critical - Security is everyone's responsibility
> **Compliance**: SOC 2, CIS Benchmarks, NIST Framework

Comprehensive security documentation covering authentication, secrets management, and infrastructure security.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Security Guide](security-guide.md)** | Comprehensive security overview |
| **[Secret Management](secret-management.md)** | Storing and protecting secrets |
| **[Secret Runtime Loading](secret-runtime.md)** | How secrets are loaded in different environments |
| **[Infrastructure Security](infrastructure-security.md)** | Container and K8s security |
| **[Security Fixes](security-fixes.md)** | Recent security improvements |

---

## 🛡️ Security Principles

### Defense in Depth

1. **Application Layer**: Input validation, authentication, authorization
2. **API Layer**: Rate limiting, CORS, CSRF protection
3. **Database Layer**: Row Level Security (RLS), encrypted connections
4. **Network Layer**: Network policies, firewalls
5. **Infrastructure Layer**: Container security, K8s policies

### Zero Trust

- Never trust, always verify
- Least privilege access
- Assume breach mentality
- Continuous validation

---

## 🔑 Authentication & Authorization

### User Roles

| Role | Access Level | Permissions |
|------|-------------|-------------|
| `admin` | Full access | All operations |
| `team_manager` | Team scope | Manage assigned team |
| `user` | Read-only | View public data |

### Authentication Flow

```
Frontend → POST /api/auth/login → Backend → Supabase Auth
                                      ↓
                                 JWT Tokens
                                      ↓
                              User Profile + Role
```

See: [Authentication Architecture](../03-architecture/authentication.md)

---

## 🔒 Secret Management

### Never Commit Secrets!

**Protected by**:
- 🔒 Pre-commit hooks (detect-secrets)
- 🔒 GitHub Actions (gitleaks, detect-secrets)
- 🔒 `.gitignore` rules
- 🔒 Daily Trivy scans

### Secret Storage

**Local Development**:
- `.env` files (gitignored)
- Environment variables

**Cloud (GKE)**:
- Kubernetes Secrets
- Managed via Helm values

**Never**:
- ❌ Hardcoded in code
- ❌ Committed to git
- ❌ Logged or printed
- ❌ Stored in plain text

See: [Secret Management Guide](secret-management.md)

---

## 🛡️ Security Scanning

### Automated Scans

**Daily**:
- Trivy (vulnerabilities, secrets, misconfigurations)
- Dependency scanning (npm audit, safety)

**On Every PR**:
- Gitleaks (secret detection)
- detect-secrets (baseline comparison)
- Container image scanning

**Weekly**:
- Infrastructure security (Checkov, tfsec)
- Full security audit

### Tools

| Tool | Purpose | Frequency |
|------|---------|-----------|
| Trivy | Vulnerabilities, secrets | Daily |
| detect-secrets | Secret detection | Pre-commit, CI |
| gitleaks | Git history scanning | CI |
| Bandit | Python security issues | CI |
| npm audit | JavaScript dependencies | CI |
| Checkov | Infrastructure as Code | Weekly |

---

## 🚨 Security Best Practices

### For Developers

```bash
# Before committing
git add .
# Pre-commit hook runs automatically (detect-secrets)

# Manual scan
detect-secrets scan --baseline .secrets.baseline

# Check for vulnerabilities
cd backend && uv run safety check
cd frontend && npm audit
```

### For DevOps

```bash
# Scan container images
trivy image missing-table/backend:latest

# Scan Kubernetes manifests
kubectl neat get deployment -o yaml | trivy config -

# Scan Terraform
trivy config terraform/
```

---

## 🔐 Compliance

### Frameworks

- **SOC 2 Type II**: Security controls and monitoring
- **CIS Benchmarks**: Container and Kubernetes security
- **NIST Cybersecurity Framework**: Overall security posture
- **OWASP Top 10**: Web application security

### Audit Trail

- All authentication events logged
- Security scan results retained
- Access logs monitored
- Incident response documented

---

## 🆘 Security Incident Response

### If You Find a Vulnerability

1. **DO NOT** open a public issue
2. Email: security@missingtable.com (if configured)
3. Or create a private security advisory on GitHub

### Suspected Breach

1. Alert the team immediately
2. Document what you observed
3. Do not investigate alone
4. Follow incident response procedure

See: [Incident Response](../07-operations/incident-response.md)

---

## 📖 Related Documentation

- **[Architecture](../03-architecture/)** - System design
- **[Deployment](../05-deployment/)** - Secure deployment
- **[Operations](../07-operations/)** - Monitoring and alerting
- **[CI/CD](../09-cicd/)** - Automated security checks

---

<div align="center">

**Security is everyone's responsibility** 🛡️

[⬆ Back to Documentation Hub](../README.md)

</div>
