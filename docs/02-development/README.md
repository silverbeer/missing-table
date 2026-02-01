# 💻 Development Guide

> **Audience**: Developers working on Missing Table
> **Prerequisites**: [Getting Started](../01-getting-started/) completed
> **Time**: Reference guide (no time limit)

This section covers daily development workflows, tools, and best practices for working on the Missing Table application.

---

## 📚 Documentation in This Section

| Document | Description |
|----------|-------------|
| **[Daily Workflow](daily-workflow.md)** | Common commands and development patterns |
| **[Environment Management](environment-management.md)** | Switching between local, dev, and prod environments |
| **[Database Operations](database-operations.md)** | Backup, restore, and database management |
| **[Schema Migrations](schema-migrations.md)** | Creating, testing, and deploying migrations |
| **[Docker Guide](docker-guide.md)** | Building images, platform considerations |
| **[Logging Standards](logging-standards.md)** | Frontend/backend logging, trace IDs, Grafana Loki |
| **[API Development](api-development.md)** | Creating new API endpoints |

---

## 🚀 Quick Reference

### Starting Development

```bash
# Start with auto-reload (RECOMMENDED for development)
./missing-table.sh dev

# Or start services individually:
cd backend && uv run python app.py     # Backend with auto-reload
cd frontend && npm run serve           # Frontend with HMR
```

### Common Development Commands

```bash
# Service Management
./missing-table.sh dev      # Start with auto-reload
./missing-table.sh status   # Check service status
./missing-table.sh logs     # View logs
./missing-table.sh tail     # Follow logs in real-time
./missing-table.sh stop     # Stop all services

# Database Operations
./scripts/db_tools.sh backup        # Create backup
./scripts/db_tools.sh restore       # Restore from latest
./scripts/db_tools.sh list          # List backups
./scripts/db_tools.sh cleanup 5     # Keep 5 most recent

# Testing
cd backend && uv run pytest                    # Backend tests
cd backend && uv run pytest --cov=.            # With coverage
cd frontend && npm test                         # Frontend tests

# Code Quality
cd backend && uv run ruff check .              # Python linting
cd frontend && npm run lint                     # JavaScript linting
```

### Environment Switching

```bash
# Switch environments
./switch-env.sh local    # Local Supabase (default)
./switch-env.sh prod     # Cloud production

# Check current environment
./switch-env.sh status
```

---

## 🏗️ Development Workflow

### 1. Daily Workflow

```bash
# Morning setup
git pull origin main
./switch-env.sh local
supabase start
./scripts/db_tools.sh restore
./missing-table.sh dev

# During development
# - Code changes trigger auto-reload automatically
# - No need to restart services!

# End of day
./scripts/db_tools.sh backup  # Optional backup
./missing-table.sh stop
```

### 2. Feature Development Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Backup before major changes
./scripts/db_tools.sh backup

# Develop and test
# ... make your changes ...
cd backend && uv run pytest
cd frontend && npm test

# Commit and push
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
```

### 3. Database Schema Changes

```bash
# 1. Backup current data
./scripts/db_tools.sh backup

# 2. Create migration
cd supabase/migrations
# Create new migration file

# 3. Apply schema changes (local only)
supabase db reset

# 4. Restore data
./scripts/db_tools.sh restore

# 5. Test thoroughly
cd backend && uv run pytest
```

---

## 🎯 Development Tips

### Auto-Reload Features

**Backend** (uvicorn --reload):
- Python file changes trigger automatic restart
- No manual restart needed
- See changes in ~1 second

**Frontend** (HMR - Hot Module Replacement):
- Vue component changes update instantly
- CSS changes apply without refresh
- State preserved during updates

### Debugging

**Backend:**
```bash
# Run with debug logging
cd backend
DEBUG=True uv run python app.py

# Or use debugger
import pdb; pdb.set_trace()
```

**Frontend:**
```bash
# Vue DevTools available in browser
# Console logging
console.log('Debug:', data)
```

### Performance

**Backend:**
```bash
# Profile slow endpoints
cd backend
uv run python -m cProfile app.py
```

**Frontend:**
```bash
# Analyze bundle size
cd frontend
npm run build --report
```

---

## 🔧 Tools & Setup

### Required Tools
- **Python 3.13+** with uv package manager
- **Node.js 16+** with npm
- **Docker** for Supabase
- **Supabase CLI** for database management

### Recommended Tools
- **VS Code** with extensions:
  - Python
  - Volar (Vue 3)
  - ESLint
  - Prettier
- **Postman** or **Bruno** for API testing
- **TablePlus** or **DBeaver** for database browsing

### Environment Files

**Backend** (`.env`, `.env.local`, `.env.dev`):
```bash
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_KEY=your_key
```

**Frontend** (`.env.local`, `.env.development`):
```bash
VUE_APP_API_URL=http://localhost:8000
VUE_APP_SUPABASE_URL=http://127.0.0.1:54321
```

---

## 🆘 Common Issues

### Port Already in Use
```bash
# Find and kill process
lsof -i :8000  # Backend
lsof -i :8081  # Frontend
kill -9 <PID>
```

### Database Connection Errors
```bash
# Restart Supabase
supabase stop
supabase start

# Verify connection
supabase status
```

### Build Errors
```bash
# Backend: Reinstall dependencies
cd backend
uv sync --reinstall

# Frontend: Clear cache
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 📖 Related Documentation

- **[Getting Started](../01-getting-started/)** - Initial setup
- **[Architecture](../03-architecture/)** - System design
- **[Testing](../04-testing/)** - Test strategy
- **[Deployment](../05-deployment/)** - Deployment guides

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
