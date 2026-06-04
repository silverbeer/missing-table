# 🚀 Getting Started with Missing Table

> **Time to Complete**: 10-15 minutes
> **Difficulty**: 🟢 Beginner
> **Prerequisites**: Basic terminal/command line knowledge

Welcome! This guide will help you get the Missing Table application running on your local machine in just a few minutes.

## What You'll Learn

- ✅ How to install all required tools
- ✅ How to start the application locally
- ✅ How to verify everything is working
- ✅ Where to go next for your first contribution

---

## Quick Start (5 Minutes)

Already have everything installed? Jump right in:

```bash
# 1. Clone the repository
git clone https://github.com/silverbeer/missing-table.git
cd missing-table

# 2. Start Supabase
supabase start

# 3. Start the application
./missing-table.sh dev

# 4. Open your browser
#    Frontend: http://localhost:8081
#    Backend API: http://localhost:8000
#    API Docs: http://localhost:8000/docs
```

That's it! 🎉

---

## Full Setup Guide

### Step 1: Prerequisites

Install these tools if you don't have them:

#### macOS
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install git node python@3.13
brew install --cask docker

# Install Python UV (modern package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Supabase CLI
brew install supabase/tap/supabase
```

#### Linux
```bash
# Install Node.js, Python
sudo apt-get update
sudo apt-get install -y git nodejs npm python3.13

# Install Docker
# Follow instructions at: https://docs.docker.com/engine/install/

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Supabase CLI
npm install -g supabase
```

#### Windows
- Install [Git for Windows](https://git-scm.com/download/win)
- Install [Node.js](https://nodejs.org/)
- Install [Python 3.13](https://www.python.org/downloads/)
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Install [UV](https://docs.astral.sh/uv/getting-started/installation/)
- Install Supabase CLI: `npm install -g supabase`

### Step 2: Clone the Repository

```bash
git clone https://github.com/silverbeer/missing-table.git
cd missing-table
```

### Step 3: Start Supabase

```bash
# Start local Supabase instance (this runs in Docker)
supabase start

# You'll see output like:
# API URL: http://localhost:55321
# DB URL: postgresql://postgres:postgres@localhost:55322/postgres
# Studio URL: http://localhost:55323
```

💡 **Tip**: Keep this terminal window open. Supabase needs to run in the background.

### Step 4: Set Up Database

```bash
# One-command setup: schema + reference data + test users
./scripts/setup-local-db.sh

# Or with match/team data from backup:
./scripts/setup-local-db.sh --restore

# This will:
# ✓ Reset database and apply consolidated schema
# ✓ Seed reference data (seasons, age groups, match types, etc.)
# ✓ Create test users (tom, tom_ifa, tom_ifa_fan, tom_club)
# ✓ Optionally restore teams and matches from backup
```

### Step 5: Start the Application

```bash
# Start both backend and frontend with auto-reload
./missing-table.sh dev

# This starts:
# - Backend API on port 8000 (with auto-reload)
# - Frontend on port 8081 (with hot module replacement)
```

Alternatively, start services individually:

```bash
# Terminal 1: Backend
cd backend
uv run python app.py

# Terminal 2: Frontend (in a new terminal)
cd frontend
npm run serve
```

### Step 6: Verify It Works

Open your browser and visit:

1. **Frontend**: http://localhost:8081
   - You should see the league standings

2. **Backend API Docs**: http://localhost:8000/docs
   - Interactive API documentation (Swagger UI)

3. **Supabase Studio**: http://localhost:55323
   - Database management interface

---

## 🎓 What's Next?

### For New Contributors
→ **[First Contribution Guide](first-contribution.md)** - Make your first PR!

### For Developers
→ **[Development Workflow](../02-development/daily-workflow.md)** - Daily commands and patterns

### For Learners
→ **[For Students Guide](../10-contributing/for-students.md)** - Learn while you code!

---

## 🆘 Troubleshooting

### Supabase won't start
```bash
# Check Docker is running
docker ps

# Stop and restart Supabase
supabase stop
supabase start
```

### Backend connection errors
```bash
# Check Supabase status
supabase status

# Verify environment variables
cat backend/.env
```

### Frontend build errors
```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Port already in use
```bash
# Find process using port 8000 (backend)
lsof -i :8000

# Find process using port 8081 (frontend)
lsof -i :8081

# Kill the process if needed
kill -9 <PID>
```

Still stuck? Check the **[Full Troubleshooting Guide](troubleshooting.md)**

---

## 📚 Documentation Index

| Document | Description |
|----------|-------------|
| **[Installation](installation.md)** | Detailed installation guide for all platforms |
| **[Local Development](local-development.md)** | Complete local development setup |
| **[First Contribution](first-contribution.md)** | Step-by-step first contribution guide |
| **[Troubleshooting](troubleshooting.md)** | Common issues and solutions |

---

## 🎯 Quick Commands Reference

```bash
# Service management
./missing-table.sh dev      # Start with auto-reload (RECOMMENDED)
./missing-table.sh start    # Start services
./missing-table.sh stop     # Stop services
./missing-table.sh status   # Show service status
./missing-table.sh logs     # View logs

# Database operations
./scripts/db_tools.sh backup    # Create backup
./scripts/db_tools.sh restore   # Restore from backup
./scripts/db_tools.sh list      # List backups

# Testing
cd backend && uv run pytest     # Run backend tests
cd frontend && npm test          # Run frontend tests

# Supabase
supabase start                   # Start Supabase
supabase stop                    # Stop Supabase
supabase status                  # Check status
```

---

<div align="center">

**Ready to contribute?** → [Make Your First Contribution](first-contribution.md)

**Need help?** → [Troubleshooting Guide](troubleshooting.md)

[⬆ Back to Documentation Hub](../README.md)

</div>
