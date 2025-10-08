# Local Development Setup Guide

This guide will help you set up the Missing Table application for local development on a new machine with the same database state as your primary development environment.

## Prerequisites Installation

### 1. Core Development Tools

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install essential development tools
brew install git node python@3.13

# Install Docker Desktop for Mac
# Download from: https://www.docker.com/products/docker-desktop/

# Install Python UV (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Supabase CLI
npm install -g supabase

# Install GitHub CLI (optional, for PR management)
brew install gh
```

### 2. Kubernetes Environment (Optional - for Helm deployments)

```bash
# Install Rancher Desktop for Kubernetes
# Download from: https://rancherdesktop.io/
# Enable Kubernetes in Rancher Desktop settings

# Install Helm (for Kubernetes deployments)
brew install helm
```

## Project Setup

### 1. Clone Repository

```bash
# Clone the repository
git clone https://github.com/silverbeer/missing-table.git
cd missing-table

# Checkout main branch (after PR is merged)
git checkout main
git pull origin main
```

### 2. Backend Setup (Python)

```bash
cd backend

# Install Python dependencies with uv
uv sync

# This creates a virtual environment and installs all dependencies
# defined in pyproject.toml and locked in uv.lock
```

### 3. Frontend Setup (Node.js)

```bash
cd frontend

# Install Node.js dependencies
npm install
```

### 4. Supabase Local Setup

```bash
# Return to project root
cd ..

# Initialize Supabase (if not already done)
npx supabase init

# Start local Supabase instance
npx supabase start

# This will output connection details like:
# API URL: http://localhost:54321
# DB URL: postgresql://postgres:postgres@localhost:54322/postgres
# Studio URL: http://localhost:54323
```

## Database Transfer Between Machines

### 1. Transfer Backup File

Transfer the fresh backup file from your primary development machine:

**Backup file location:**
```
/Users/silverbeer/gitrepos/missing-table/backups/database_backup_20250909_114614.json
```

**Options for transfer:**
- AirDrop
- USB drive  
- Cloud storage (iCloud, Google Drive, etc.)
- Git LFS (if configured)
- Network transfer

### 2. Restore Database on New Machine

```bash
# Place the backup file in the backups/ directory
# Then restore using the db_tools script

./scripts/db_tools.sh restore database_backup_20250909_114614.json

# Or restore from latest backup in the directory
./scripts/db_tools.sh restore
```

### 3. Verify Database Restoration

```bash
# List available backups to confirm
./scripts/db_tools.sh list

# The restore script will show:
# ✓ Total records restored: 502
# ✓ Teams: 21, Games: 347, etc.
```

## Development Workflow

### 1. Start Full Development Stack

```bash
# Start both frontend and backend
./missing-table.sh start

# This starts:
# - Backend API: http://localhost:8000
# - Frontend: http://localhost:8080
# - Supabase Studio: http://localhost:54323
```

### 2. Individual Service Startup

```bash
# Backend only
cd backend && uv run python app.py

# Frontend only  
cd frontend && npm run serve

# Supabase only
npx supabase start
```

### 3. Verify Everything Works

1. **Frontend:** http://localhost:8080
   - Should show league standings
   - Teams and games should match primary development machine data

2. **Backend API:** http://localhost:8000/docs
   - Swagger UI should be accessible
   - Test endpoints should return data

3. **Supabase Studio:** http://localhost:54323
   - Browse tables to verify data transfer
   - Check teams, games, user_profiles tables

## Testing and Validation

### 1. Run Tests

```bash
# Backend tests
cd backend && uv run pytest

# Frontend linting
cd frontend && npm run lint
```

### 2. Database Integrity Check

```bash
# Create a test backup to verify restore process worked
./scripts/db_tools.sh backup

# Compare record counts with primary development machine
# Should match: 21 teams, 347 games, etc.
```

### 3. Full Stack Integration Test

```bash
# Run comprehensive uptime test (optional)
cd backend && uv run python ../scripts/uptime_test.py

# This verifies:
# - Database connectivity
# - API endpoints
# - Frontend accessibility
# - Authentication flow
```

## Production Deployment (Optional)

### 1. Docker Compose

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access:
# - Frontend: http://localhost:8080
# - Backend: http://localhost:8000
```

### 2. Kubernetes with Helm

```bash
# Deploy to local Kubernetes cluster
cd helm && ./deploy-helm.sh

# This will:
# - Build Docker images
# - Deploy to Kubernetes
# - Set up LoadBalancer services
```

## Troubleshooting

### Common Issues

1. **Supabase won't start:**
   ```bash
   # Check if ports are in use
   lsof -i :54321 -i :54322 -i :54323
   
   # Stop and restart Supabase
   npx supabase stop
   npx supabase start
   ```

2. **Python dependencies issues:**
   ```bash
   # Recreate virtual environment
   uv sync --reinstall
   ```

3. **Database connection errors:**
   ```bash
   # Verify Supabase is running
   npx supabase status
   
   # Check connection string in backend/.env
   ```

4. **Frontend build issues:**
   ```bash
   # Clear npm cache and reinstall
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

## Next Steps

1. **Merge PR:** Review and merge PR #6 (v1.4 → main) on GitHub
2. **Sync changes:** `git pull origin main` to get merged changes
3. **Start development:** Begin working on new features with identical database state
4. **Backup routine:** Set up regular backups with `./scripts/db_tools.sh backup`

## Summary

After following this guide, you'll have:
- ✅ Complete development environment on new machine
- ✅ Identical database state from primary development machine (502 records)  
- ✅ All services running locally (frontend, backend, database)
- ✅ Production deployment capabilities (Docker + Kubernetes)
- ✅ Testing and validation tools

Your new machine will be fully synchronized with your primary development environment.