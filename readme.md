# Sports League Management System

A comprehensive web application for managing sports leagues, including teams, games, standings, and administrative functions. Features a modern FastAPI backend with authentication and a Vue.js frontend with admin panel.

## 🌟 Features

- **League Management**: Create and manage teams, games, seasons, and divisions
- **Authentication & Authorization**: Role-based access control (Admin, Team Manager, User)
- **Admin Panel**: Complete CRUD operations for all data types
- **Real-time Standings**: Dynamic league tables with filtering
- **Game Scheduling**: Schedule and manage league, friendly, and tournament games
- **Team Types**: Support for league teams, guest teams, and academy teams
- **Modern UI**: Responsive design with Tailwind CSS

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend      │    │   Supabase      │
│  (Vue.js)       │◄──►│    (FastAPI)     │◄──►│  (PostgreSQL)   │
│  localhost:8081 │    │  localhost:8000  │    │ localhost:54321 │
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

### 1. Clone and Setup

```bash
git clone <repository-url>
cd missing-table
```

### 2. Start Supabase

```bash
# Initialize and start local Supabase
supabase init
supabase start
```

### 3. Start Backend

```bash
cd backend
# Environment variables are loaded from .env.local automatically
uv run python app.py
```

### 4. Start Frontend

```bash
cd ../frontend
npm install
npm run serve
```

### 5. Access the Application

- **Frontend**: http://localhost:8081
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Supabase Studio**: http://localhost:54323

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

### Adding New Features

1. **Backend**: Add endpoints in `app.py`, implement business logic in DAO layer
2. **Frontend**: Create Vue components, update stores for state management
3. **Database**: Create migrations for schema changes
4. **Tests**: Add tests for new functionality

## 📚 Documentation

- **Backend**: See [backend/README.md](backend/README.md) for detailed backend documentation
- **Tests**: See [backend/tests/README.md](backend/tests/README.md) for testing guide
- **Development**: See [CLAUDE.md](CLAUDE.md) for development workflow and guidelines

## 🛠️ Technologies Used

- **Backend**: FastAPI, Python 3.13, uv, Supabase, PyJWT
- **Frontend**: Vue.js 3, Pinia, Tailwind CSS, Vite
- **Database**: PostgreSQL (via Supabase)
- **Authentication**: Supabase Auth with JWT
- **Testing**: pytest, Vue Test Utils
- **Development**: Supabase CLI, Docker

## 🔄 Recent Updates (v1.1)

- ✅ **Enhanced Authentication**: Proactive token refresh and improved session management
- ✅ **Admin Panel**: Complete games management with edit/delete functionality
- ✅ **UI Improvements**: Default to U14 age group and 2025-2026 season
- ✅ **Error Handling**: Better error messages and session expiration handling
- ✅ **Role-based Access**: Comprehensive admin endpoints with proper authorization

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

This project is licensed under the MIT License.
