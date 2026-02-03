# Secret Runtime Loading - Complete Flow

This document explains how secrets are loaded at runtime in different environments.

## Overview

The application uses **different secret loading strategies** depending on the environment:

- **Local Development**: `.env` files (gitignored)
- **GKE/Production**: Kubernetes Secrets → Environment Variables
- **Frontend**: Build-time compilation (not runtime)

---

## Backend Secret Loading

### Local Development

**How it works:**
1. Developer creates `.env.local` from example
2. Backend uses `python-dotenv` to load from `.env` files
3. Environment variables are read via `os.getenv()`

**File:** `backend/app.py`
```python
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Read secrets
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
```

**Available .env files:**
- `backend/.env` - Default (git tracked, no secrets)
- `backend/.env.local` - Local Supabase (gitignored)
- `backend/.env.prod` - Cloud prod environment (gitignored)
- `backend/.env.example` - Template (git tracked)

**Setup:**
```bash
# Copy example
cp backend/.env.example backend/.env.local

# Edit with real values
vim backend/.env.local

# Start backend
cd backend && uv run python app.py
# Automatically loads .env.local
```

### GKE/Production (Kubernetes)

**How it works:**
1. Secrets stored in `helm/missing-table/values-dev.yaml` (gitignored)
2. Helm creates Kubernetes Secret in cluster
3. Pod deployment references Secret via `secretKeyRef`
4. Kubernetes injects secrets as environment variables
5. Backend reads via `os.getenv()`

**Flow:**
```
values-dev.yaml (local file, gitignored)
         ↓
    helm upgrade
         ↓
Kubernetes Secret (in cluster)
  name: missing-table-secrets
         ↓
Pod Deployment (secretKeyRef)
         ↓
Environment Variables in Container
         ↓
Backend reads: os.getenv("DATABASE_URL")
```

**File:** `helm/missing-table/templates/secrets.yaml`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: missing-table-secrets
  namespace: {{ .Values.namespace }}
stringData:
  database-url: {{ .Values.secrets.databaseUrl | quote }}
  supabase-service-key: {{ .Values.secrets.supabaseServiceKey | quote }}
  # ... other secrets
```

**File:** `helm/missing-table/templates/backend.yaml`
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

**Setup:**
```bash
# Create values file from example
cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml

# Add real secrets
vim helm/missing-table/values-dev.yaml

# Deploy (creates Secret automatically)
helm upgrade missing-table ./missing-table -n missing-table-dev \
  --values ./missing-table/values-dev.yaml --wait
```

**Verify:**
```bash
# Check Secret exists
kubectl get secret missing-table-secrets -n missing-table-dev

# View Secret keys (not values)
kubectl describe secret missing-table-secrets -n missing-table-dev

# Check pod environment (only shows references)
kubectl describe pod -n missing-table-dev | grep -A 5 "Environment:"
```

---

## Frontend Secret Loading

### ⚠️ Important: Frontend Secrets are Build-Time, Not Runtime

The frontend is a **static Vue.js application**. Secrets are compiled into the JavaScript bundle at **build time**, not loaded at runtime.

### Local Development

**How it works:**
1. Developer creates `.env.local`
2. Vue CLI reads `.env` files during `npm run serve`
3. Variables prefixed with `VUE_APP_` are compiled into the code
4. No runtime environment variable loading

**Available .env files:**
- `frontend/.env` - Default development (git tracked, public values only)
- `frontend/.env.local` - Local Supabase (gitignored)
- `frontend/.env.prod` - Cloud prod environment (gitignored)
- `frontend/.env.production` - Production build config (gitignored)

**Setup:**
```bash
# Copy example
cp frontend/.env.local.example frontend/.env.local

# Edit with values
vim frontend/.env.local

# Start dev server
cd frontend && npm run serve
# Vue CLI automatically loads .env.local
```

**File:** `frontend/.env.local`
```bash
VUE_APP_API_URL=http://localhost:8000
VUE_APP_SUPABASE_URL=http://127.0.0.1:54321
VUE_APP_SUPABASE_ANON_KEY=your-local-anon-key
```

**How Vue.js uses these:**
```javascript
// In frontend code
const apiUrl = process.env.VUE_APP_API_URL
const supabase = createClient(
  process.env.VUE_APP_SUPABASE_URL,
  process.env.VUE_APP_SUPABASE_ANON_KEY
)
```

### GKE/Production (Docker Build)

**How it works:**
1. Secrets stored in `frontend/build.env` (gitignored)
2. Docker build reads `build.env` as build arguments
3. Build arguments become ENV vars during `npm run build`
4. Vue CLI compiles ENV vars into static JavaScript
5. **Final bundle contains hardcoded values** (no runtime loading)

**Flow:**
```
build.env (local file, gitignored)
         ↓
docker build --build-arg VUE_APP_API_URL=...
         ↓
Dockerfile: ENV VUE_APP_API_URL=$VUE_APP_API_URL
         ↓
RUN npm run build (Vue CLI reads ENV)
         ↓
Compiled JavaScript bundle (values hardcoded)
         ↓
Static files served by nginx/serve
         ↓
Browser executes JavaScript (values already in code)
```

**File:** `frontend/Dockerfile`
```dockerfile
# Build arguments (from build.env)
ARG VUE_APP_API_URL
ARG VUE_APP_SUPABASE_URL
ARG VUE_APP_SUPABASE_ANON_KEY

# Set as environment variables for build
ENV VUE_APP_API_URL=$VUE_APP_API_URL
ENV VUE_APP_SUPABASE_URL=$VUE_APP_SUPABASE_URL
ENV VUE_APP_SUPABASE_ANON_KEY=$VUE_APP_SUPABASE_ANON_KEY

# Build the application (values compiled in)
RUN npm run build
```

**Setup:**
```bash
# Create build config from example
cp frontend/build.env.example frontend/build.env

# Add environment-specific values
vim frontend/build.env

# Build (script loads build.env automatically)
./scripts/build-and-push.sh --env dev --frontend-only
```

**Important Notes:**
- ✅ Frontend secrets are **public by design** (Supabase anon key)
- ✅ API URL is public (browser needs to know where to connect)
- ❌ **Cannot change at runtime** - requires rebuild to update
- ✅ Different builds for different environments (dev/staging/prod)

---

## Environment Comparison Table

| Aspect | Local Development | GKE/Production |
|--------|------------------|----------------|
| **Backend Secrets** | `.env` files (dotenv) | Kubernetes Secrets → ENV |
| **Frontend Secrets** | `.env` files (Vue CLI) | Build args → Compiled |
| **Secret Storage** | Local filesystem | Kubernetes etcd (encrypted) |
| **Runtime Loading** | File read on startup | ENV vars from Secret |
| **Update Process** | Edit file, restart | Update values, helm upgrade |
| **Security** | .gitignore protection | K8s RBAC + encryption |

---

## Complete Environment Setup

### Local Development (First Time)

```bash
# 1. Backend secrets
cp backend/.env.example backend/.env.local
vim backend/.env.local  # Add real values

# 2. Frontend config
cp frontend/.env.local.example frontend/.env.local
vim frontend/.env.local  # Add real values

# 3. Start services
./missing-table.sh start
```

### GKE Development (First Time)

```bash
# 1. Backend secrets (Helm values)
cp helm/missing-table/values-dev.yaml.example helm/missing-table/values-dev.yaml
vim helm/missing-table/values-dev.yaml  # Add real secrets

# 2. Frontend build config
cp frontend/build.env.example frontend/build.env
vim frontend/build.env  # Add environment-specific values

# 3. Build and push Docker images
./scripts/build-and-push.sh --env dev

# 4. Deploy with Helm
cd helm
helm upgrade missing-table ./missing-table \
  -n missing-table-dev \
  --values ./missing-table/values-dev.yaml \
  --wait
```

---

## Secret Update Procedures

### Update Local Secrets

**Backend:**
```bash
vim backend/.env.local
./missing-table.sh restart
```

**Frontend:**
```bash
vim frontend/.env.local
# Restart dev server (Ctrl+C, then npm run serve)
```

### Update GKE Secrets

**Backend (Runtime Secrets):**
```bash
# 1. Update values file
vim helm/missing-table/values-dev.yaml

# 2. Upgrade deployment (updates Secret)
helm upgrade missing-table ./missing-table -n missing-table-dev \
  --values ./missing-table/values-dev.yaml --wait

# 3. Restart pods to pick up new secrets
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
```

**Frontend (Build-Time Values):**
```bash
# 1. Update build config
vim frontend/build.env

# 2. Rebuild and push image
./scripts/build-and-push.sh --env dev --frontend-only

# 3. Restart deployment to use new image
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
```

---

## Troubleshooting

### Backend Not Reading Secrets (Local)

**Problem:** Backend can't connect to database

**Check:**
```bash
# Verify .env file exists
ls -la backend/.env.local

# Test dotenv loading
cd backend
uv run python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DATABASE_URL'))"
```

**Solution:** Ensure .env.local exists and has correct values

### Backend Not Reading Secrets (GKE)

**Problem:** Backend pod crashing or can't access database

**Check:**
```bash
# Verify Secret exists
kubectl get secret missing-table-secrets -n missing-table-dev

# Check pod environment
kubectl exec -n missing-table-dev deployment/missing-table-backend -- env | grep DATABASE_URL

# Check pod logs
kubectl logs -n missing-table-dev deployment/missing-table-backend
```

**Solution:**
```bash
# Update Secret
helm upgrade missing-table ./missing-table -n missing-table-dev \
  --values ./missing-table/values-dev.yaml --wait

# Restart pods
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
```

### Frontend Using Wrong API URL

**Problem:** Frontend calling old API URL

**Reason:** Frontend values are **compiled at build time**, not runtime

**Check:**
```bash
# What's in the current build?
curl -s https://dev.missingtable.com/js/app.*.js | grep -o 'https://[^"]*' | head -5
```

**Solution:** Rebuild frontend with correct values
```bash
# Update build.env
vim frontend/build.env

# Rebuild
./scripts/build-and-push.sh --env dev --frontend-only

# Deploy
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev
```

---

## Security Best Practices

### Local Development

✅ **DO:**
- Keep `.env` files in `.gitignore`
- Use separate `.env.local`, `.env.prod`
- Store backups in password manager, not files
- Use weak passwords for local-only services

❌ **DON'T:**
- Commit `.env` files to git
- Use production secrets locally
- Share `.env` files via Slack/email
- Copy production DB to local

### GKE/Production

✅ **DO:**
- Use Kubernetes Secrets (encrypted at rest)
- Rotate secrets regularly (every 90 days)
- Use different secrets per environment
- Audit Secret access with RBAC
- Keep `values-*.yaml` files gitignored

❌ **DON'T:**
- Commit `values-*.yaml` to git
- Use same secrets across environments
- Share values files in unencrypted channels
- Give all developers prod access

---

## Related Documentation

- [Secret Management Guide](./SECRET_MANAGEMENT.md) - Comprehensive secret management
- [GKE HTTPS Setup](./GKE_HTTPS_DOMAIN_SETUP.md) - HTTPS and domain configuration
- [Quick Reference](./HTTPS_QUICK_REFERENCE.md) - Common commands

---

**Last Updated:** October 4, 2025
