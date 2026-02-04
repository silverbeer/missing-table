<div align="center">

# ⚽ Missing Table

**A modern, full-stack web application for managing competitive youth soccer leagues**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue.js 3](https://img.shields.io/badge/Vue.js-3.x-brightgreen.svg)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Documentation](docs/README.md) • [Infrastructure](https://github.com/silverbeer/missingtable-platform-bootstrap) • [Contributing](docs/10-contributing/README.md) • [Report Bug](https://github.com/silverbeer/missing-table/issues)

</div>

---

## ✨ What is Missing Table?

Missing Table is a **production-ready web application** designed for managing competitive youth soccer leagues across multiple age groups and regions. Built with modern technologies and best practices, it's perfect for:

- 🏆 **League Administrators** - Manage teams, games, and standings
- 👨‍💻 **Developers** - Learn modern web development with a real-world application
- 🎓 **Students** - Gain hands-on experience with professional tools and workflows
- 🤝 **Contributors** - Make meaningful contributions to an active open-source project

---

## 🎯 Key Features

<table>
<tr>
<td width="50%">

### 📊 League Management
- Complete team, game, and season management
- Support for multiple age groups (U13-U19)
- Division and game type categorization
- Real-time standings calculation

### 🔐 Authentication & Security
- Role-based access control (Admin, Team Manager, User)
- JWT-based authentication
- Secure secret management
- Multi-layer security scanning

</td>
<td width="50%">

### 💻 Modern Tech Stack
- **Backend**: FastAPI (Python 3.13+)
- **Frontend**: Vue.js 3 with Composition API
- **Database**: PostgreSQL via Supabase
- **Infrastructure**: 100% IaC via [platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap)

### 🧪 Quality & Testing
- 80%+ test coverage goal
- Automated CI/CD pipelines
- Contract testing with Schemathesis
- Comprehensive documentation

</td>
</tr>
</table>

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend      │    │   Supabase      │
│  (Vue.js)       │◄──►│    (FastAPI)     │◄──►│  (PostgreSQL)   │
│  localhost:8080 │    │  localhost:8000  │    │ localhost:54321 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                │ Studio: :54323  │
                                                │ DB: :54322      │
                                                └─────────────────┘
```

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+** - Modern Python version
- **uv** - Modern Python package manager ([Install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js 16+** and **npm** - For the frontend
- **Supabase CLI** - For local development (`brew install supabase/tap/supabase`)
- **Docker** - Required for Supabase CLI

## 🚀 Quick Start

Get up and running in **less than 5 minutes**:

```bash
# 1. Clone the repository
git clone https://github.com/silverbeer/missing-table.git
cd missing-table

# 2. Start Supabase
supabase start

# 3. Restore database and start services
./scripts/db_tools.sh restore
./missing-table.sh dev

# 4. Open your browser
# Frontend: http://localhost:8080
# Backend API: http://localhost:8000/docs
```

**First time?** → See the **[Complete Getting Started Guide](docs/01-getting-started/README.md)** for detailed setup instructions.

---

## 📚 Comprehensive Documentation

We've built **world-class documentation** to help you succeed:

### 🎓 For Students & Learners

**New to open source?** Perfect! This project welcomes beginners.

- **[For Students Guide](docs/10-contributing/for-students.md)** 🌟 - Start here if you're learning to code!
- **[First Contribution](docs/01-getting-started/first-contribution.md)** - Make your first pull request
- **[Contributing Guide](docs/10-contributing/README.md)** - Contribution guidelines and code of conduct

### 💻 For Developers

**Working on the codebase?** Everything you need is documented:

- **[Getting Started](docs/01-getting-started/)** - Complete setup guide
- **[Development Guide](docs/02-development/)** - Daily workflows and commands
- **[Architecture](docs/03-architecture/)** - System design and patterns
- **[Testing](docs/04-testing/)** - Testing strategy and quality metrics
- **[API Documentation](http://localhost:8000/docs)** - Interactive Swagger UI (when running)

### 🚀 For DevOps

**Deploying or managing infrastructure?**

- **[Platform Bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap)** - 100% IaC, ArgoCD, Monitoring
- **[Deployment Guide](docs/05-deployment/)** - Docker, Kubernetes, Helm
- **[Security](docs/06-security/)** - Security practices and compliance
- **[Operations](docs/07-operations/)** - Monitoring, backups, incidents
- **[CI/CD](docs/09-cicd/)** - Pipeline and quality gates

### 📖 **[Complete Documentation Hub](docs/README.md)**

## ⚠️ Development Notes

### Node.js Version Warnings
When running `npm install`, you may see warnings about Node.js engine versions. These are safe to ignore as the package.json has been updated to support Node.js 18+ and npm 9+.

### Security Vulnerabilities
The npm audit may report security vulnerabilities in development dependencies. These are primarily in the Vue CLI build tools and do not affect production runtime security.

## 📁 Project Structure

```
missing-table/
├── backend/                 # FastAPI backend
│   ├── app.py              # Main application
│   ├── auth.py             # Authentication & authorization
│   ├── dao/                # Data Access Objects
│   ├── scripts/            # Setup and migration scripts
│   ├── tests/              # Test suite
│   └── docs/               # Backend documentation
├── frontend/               # Vue.js frontend
│   ├── src/
│   │   ├── components/     # Vue components
│   │   │   └── admin/      # Admin panel components
│   │   └── stores/         # Pinia stores
│   └── public/
├── supabase/              # Database migrations
└── CLAUDE.md              # Development guide
```

## 🔐 Authentication

The system supports three user roles:

- **Admin**: Full access to all features and admin panel
- **Team Manager**: Can manage their assigned team
- **User**: Read-only access to public data

### Default Admin User

For development, create an admin user:
1. Sign up through the application
2. Use Supabase Studio to set the user's role to 'admin' in the `user_profiles` table

## 🎯 Key Features

### Admin Panel
- **Teams**: Add, edit, delete teams with age group and division assignments
- **Games**: Schedule, edit, and delete games with score tracking
- **Seasons**: Manage season periods and active seasons
- **Age Groups**: Configure age categories (U13, U14, etc.)
- **Divisions**: Manage geographical or skill-based divisions

### Game Management
- **Multiple Game Types**: League, Friendly, Tournament games
- **Team Filtering**: Teams are filtered based on game type and age group
- **Score Tracking**: Add scores for completed games
- **Scheduling**: Schedule future games without scores

### Standings
- **Dynamic Tables**: Real-time league standings calculations
- **Filtering**: Filter by season, age group, division, and game type
- **Statistics**: Points, wins, draws, losses, goals for/against, goal difference

## 🧪 Testing

### Backend Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test categories
uv run pytest -m integration  # Database tests
uv run pytest -m e2e         # End-to-end API tests
```

### Frontend Tests

```bash
cd frontend
npm run test        # Unit tests
npm run test:e2e    # End-to-end tests
npm run lint        # Linting
```

## 🔧 Development

### Environment Configuration

Create `.env.local` in the backend directory:

```bash
# Local Supabase Configuration
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
```

Get your keys by running `supabase status` after starting the local instance.

### Database Migrations

```bash
# Apply new migrations
supabase db reset

# Create new migration
supabase migration new migration_name
```

### Database Backup & Restore

The project includes a comprehensive backup and restore system for development and production use:

#### Quick Backup Commands

```bash
# Create dual backup (JSON + SQL formats)
./scripts/db_tools.sh backup

# List available backups
./scripts/db_tools.sh list

# Restore from latest backup
./scripts/db_tools.sh restore

# Restore from specific backup
./scripts/db_tools.sh restore database_backup_20231220_143022.json

# Clean up old backups (keep 10)
./scripts/db_tools.sh cleanup
```

#### Backup Types

**Development Backups** (JSON Format):
- Fast and lightweight
- Selective table restore
- Cross-environment compatible
- Dependency-aware restoration
- Perfect for development iterations

**Production Backups** (SQL Format):
- Standard PostgreSQL dump format
- Industry-standard restoration process
- Disaster recovery compatible
- Can be used with any PostgreSQL instance

#### Backup Workflow

1. **Automatic Dual Backup**: Every backup creates both JSON and SQL formats
2. **Timestamped Files**: All backups include timestamp for easy identification
3. **Metadata Tracking**: JSON backups include table counts and file sizes
4. **Cleanup Management**: Automatic cleanup prevents disk space bloat

#### Advanced Operations

```bash
# Reset database and repopulate with basic data
./scripts/db_tools.sh reset

# Production backup (when live)
./scripts/db_tools.sh backup-prod

# Keep only 5 most recent backups
./scripts/db_tools.sh cleanup 5
```

#### Backup Location

All backups are stored in the `backups/` directory:
- `database_backup_YYYYMMDD_HHMMSS.json` - Development format
- `database_backup_YYYYMMDD_HHMMSS.sql` - Production format

### Adding New Features

1. **Backend**: Add endpoints in `app.py`, implement business logic in DAO layer
2. **Frontend**: Create Vue components, update stores for state management
3. **Database**: Create migrations for schema changes
4. **Tests**: Add tests for new functionality

## 🤝 Contributing

We **love** contributions! This project is designed to be welcoming to developers of all skill levels.

### Ways to Contribute

- 🐛 **Fix bugs** - Find and fix issues
- ✨ **Add features** - Implement new functionality
- 📚 **Improve docs** - Help others understand the project
- 🧪 **Write tests** - Increase code coverage
- 💡 **Share ideas** - Propose improvements

### Getting Started with Contributing

1. **[For Students](docs/10-contributing/for-students.md)** - Perfect for beginners! 🎓
2. **[First Contribution](docs/01-getting-started/first-contribution.md)** - Step-by-step guide
3. **[Contributing Guidelines](docs/10-contributing/README.md)** - Full contributor guide

**Find a Good First Issue** → [Issues labeled `good-first-issue`](https://github.com/silverbeer/missing-table/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

## 🛠️ Technologies Used

- **Backend**: FastAPI, Python 3.13, uv, Supabase, PyJWT
- **Frontend**: Vue.js 3, Pinia, Tailwind CSS, Vite
- **Database**: PostgreSQL (via Supabase)
- **Authentication**: Supabase Auth with JWT
- **Testing**: pytest, Vue Test Utils
- **Development**: Supabase CLI, Docker

## 🏗️ Infrastructure

Infrastructure is managed in a **separate repository** following GitOps best practices:

**[missingtable-platform-bootstrap](https://github.com/silverbeer/missingtable-platform-bootstrap)**

This repository contains:
- **100% Infrastructure as Code** - All infrastructure defined in Terraform/OpenTofu
- **ArgoCD** - GitOps-based continuous deployment
- **Grafana Stack** - Full observability (Loki, Tempo, Grafana dashboards)
- **Linode Kubernetes (LKE)** - Production Kubernetes cluster
- **Helm Charts** - Application deployment configurations

**Why separate repos?**
- Clear separation of concerns (app code vs infrastructure)
- Different change cadences and review processes
- Follows GitOps best practices
- Enables independent scaling of teams

## 📊 Quick Commands Reference

```bash
# Service Management
./missing-table.sh dev      # Start with auto-reload (RECOMMENDED)
./missing-table.sh status   # Show service status
./missing-table.sh logs     # View logs

# Database Operations
./scripts/db_tools.sh backup    # Create backup
./scripts/db_tools.sh restore   # Restore from backup
./scripts/db_tools.sh list      # List backups

# Testing
cd backend && uv run pytest     # Backend tests
cd frontend && npm test         # Frontend tests

# Environment Switching
./switch-env.sh local    # Local development
./switch-env.sh prod     # Production (use with caution)
```

**Full command reference** → [Daily Workflow Guide](docs/02-development/daily-workflow.md)

---

## 🚨 Troubleshooting

### Common Issues

1. **Backend won't start**: Check if Supabase is running with `supabase status`
2. **Authentication errors**: Verify environment variables are set correctly
3. **Empty data**: Run migration scripts to populate reference data
4. **Frontend build errors**: Clear node_modules and reinstall dependencies

### Getting Help

- Check the detailed documentation in each component's README
- Review the CLAUDE.md file for development guidelines
- Check Supabase Studio for database issues
- Use the API documentation at http://localhost:8000/docs

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support & Community

### Getting Help

- 📖 **[Documentation](docs/README.md)** - Comprehensive guides
- 🐛 **[Issues](https://github.com/silverbeer/missing-table/issues)** - Report bugs
- 💬 **[Discussions](https://github.com/silverbeer/missing-table/discussions)** - Ask questions

### Community

- ⭐ **Star this repo** if you find it useful!
- 🐦 **Share on Twitter** to help others discover it
- 💼 **Add to LinkedIn** to showcase your contributions

---

<div align="center">

**Ready to get started?**

[📖 Read the Docs](docs/README.md) • [🚀 Quick Start](docs/01-getting-started/README.md) • [🤝 Contribute](docs/10-contributing/README.md)

Made with ❤️ by the Missing Table community

</div>
