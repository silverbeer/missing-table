# Secret Management

**SECURITY NOTICE:** This document describes how secrets are managed in the Missing Table application.

## Overview

The application uses **Kubernetes Secrets** to manage sensitive credentials in the GKE deployment. Secrets are never committed to git.

## Architecture

```
values-dev.yaml (local only, gitignored)
         ↓
    Helm Chart
         ↓
  Kubernetes Secret (in cluster)
         ↓
    Pod Environment Variables
```

## Secret Storage

### What Gets Stored as Secrets

- **Database credentials** - Connection strings with passwords
- **Supabase Service Key** - Admin access key (very sensitive!)
- **Supabase JWT Secret** - For token verification
- **Service Account Secrets** - For service-to-service authentication

### What's NOT Secret (Safe to Commit)

- **Supabase Anon Key** - Public-facing key (compiled into frontend)
- **Supabase URL** - Public endpoint
- **CORS origins** - Domain configuration
- **Environment settings** - Log levels, feature flags

## Setup Instructions

### 1. Initial Setup

```bash
# Copy the example file
cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml

# Edit with your actual secrets
vim helm/missing-table/values-dev.yaml
```

### 2. Fill in Secrets

Update the `secrets:` section in `values-dev.yaml`:

```yaml
secrets:
  # Database credentials
  databaseUrl: "postgresql://user:PASSWORD@host:port/database"

  # Supabase credentials (from Supabase Dashboard > Settings > API)
  supabaseUrl: "https://your-project.supabase.co"
  supabaseAnonKey: "your-anon-key-here"
  supabaseServiceKey: "your-service-role-key-here"  # KEEP SECRET!
  supabaseJwtSecret: "your-jwt-secret-here"

  # Application secrets
  serviceAccountSecret: "generate-random-secret-here"
```

### 3. Deploy with Helm

```bash
cd helm

# Deploy with secrets
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

Helm will automatically create a Kubernetes Secret named `missing-table-secrets` in the cluster.

### 4. Verify Secret is Created

```bash
# Check if secret exists
kubectl get secret missing-table-secrets -n missing-table-dev

# View secret keys (not values)
kubectl describe secret missing-table-secrets -n missing-table-dev
```

## How It Works

### 1. Helm Template (`templates/secrets.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "missing-table.fullname" . }}-secrets
  namespace: {{ .Values.namespace }}
type: Opaque
stringData:
  database-url: {{ .Values.secrets.databaseUrl | quote }}
  supabase-service-key: {{ .Values.secrets.supabaseServiceKey | quote }}
  # ... other secrets
```

### 2. Backend Deployment Uses Secret

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: missing-table-secrets
        key: database-url
  - name: SUPABASE_SERVICE_KEY
    valueFrom:
      secretKeyRef:
        name: missing-table-secrets
        key: supabase-service-key
```

### 3. Application Reads from Environment

The FastAPI backend reads secrets from environment variables:

```python
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
```

## Git Protection

### .gitignore Rules

```gitignore
# Ignore all values files with secrets
helm/**/values-*.yaml

# Except example files
!helm/**/values-*.yaml.example
```

This ensures:
- ✅ `values-dev.yaml.example` is committed (template)
- ❌ `values-dev.yaml` is NEVER committed (contains real secrets)
- ❌ `values-prod.yaml` is NEVER committed (contains real secrets)

## Security Best Practices

### ✅ DO

1. **Use different secrets for each environment** (dev, staging, prod)
2. **Rotate secrets regularly** (every 90 days minimum)
3. **Use strong random secrets** (generate with `openssl rand -base64 32`)
4. **Limit access** to values files on your local machine
5. **Use Workload Identity** for GCP service authentication (advanced)
6. **Store backup secrets securely** (password manager, not files)

### ❌ DON'T

1. **Never commit values-*.yaml files** to git
2. **Never share secrets** via Slack, email, or unencrypted channels
3. **Never use production secrets** in development
4. **Never log secrets** in application code
5. **Never hardcode secrets** in source code

## Secret Rotation

If secrets are exposed (e.g., committed to git), rotate immediately:

### 1. Rotate Supabase Secrets

```bash
# In Supabase Dashboard:
# Settings > API > Generate new service_role key
# Settings > Database > Reset JWT secret
```

### 2. Rotate Database Password

```bash
# In Supabase Dashboard:
# Settings > Database > Reset password
```

### 3. Update values-dev.yaml

```bash
vim helm/missing-table/values-dev.yaml
# Update with new secrets
```

### 4. Redeploy

```bash
cd helm
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

### 5. Restart Pods (if needed)

```bash
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
```

## Alternative: Google Secret Manager (Advanced)

For production, consider using Google Secret Manager with Workload Identity:

### Benefits
- Centralized secret management
- Automatic secret rotation
- Audit logging
- Fine-grained access control

### Implementation
```bash
# Store secret in Google Secret Manager
gcloud secrets create database-url --data-file=-

# Grant pod access via Workload Identity
gcloud iam service-accounts add-iam-policy-binding \
  missing-table-backend@PROJECT_ID.iam.gserviceaccount.com \
  --member=serviceAccount:PROJECT_ID.svc.id.goog[missing-table-dev/missing-table-backend] \
  --role=roles/secretmanager.secretAccessor
```

See [External Secrets Operator](https://external-secrets.io/) for Kubernetes integration.

## Troubleshooting

### Secret Not Found Error

```
Error: secret "missing-table-secrets" not found
```

**Solution:** Deploy with Helm to create the secret:
```bash
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml
```

### Permission Denied

```
Error: Forbidden: User cannot get secret
```

**Solution:** Check RBAC permissions:
```bash
kubectl auth can-i get secrets -n missing-table-dev
```

### Wrong Secret Value

**Solution:** Update values file and redeploy:
```bash
vim helm/missing-table/values-dev.yaml
helm upgrade missing-table ./missing-table -n missing-table-dev --values ./missing-table/values-dev.yaml
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
```

## Files Reference

```
missing-table/
├── .gitignore                              # Protects secrets from git
├── helm/missing-table/
│   ├── templates/
│   │   ├── secrets.yaml                    # Secret manifest template
│   │   └── backend.yaml                    # Uses secretKeyRef
│   ├── values-dev.yaml                     # REAL secrets (gitignored)
│   ├── values-dev.yaml.example             # Template (committed)
│   ├── values-prod.yaml                    # REAL secrets (gitignored)
│   └── values-prod.yaml.example            # Template (committed)
└── docs/
    └── SECRET_MANAGEMENT.md                # This file
```

## Emergency Procedures

### If Secrets Are Committed to Git

1. **DO NOT just delete the commit** - secrets remain in git history
2. **Immediately rotate ALL exposed secrets** in Supabase
3. **Use BFG Repo-Cleaner or git-filter-repo** to remove from history:
   ```bash
   # WARNING: This rewrites history
   git filter-repo --path helm/missing-table/values-dev.yaml --invert-paths
   ```
4. **Force push** (if remote exists):
   ```bash
   git push origin --force --all
   ```
5. **Notify team** to re-clone the repository

### If Secrets Are Leaked Publicly

1. **Rotate ALL secrets immediately**
2. **Review access logs** for unauthorized access
3. **Consider resetting the database** if compromised
4. **File incident report** (if required by your organization)

---

**Last Updated:** October 3, 2025
