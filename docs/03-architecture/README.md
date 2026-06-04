# 🏗️ Architecture Documentation

> **Audience**: Developers, architects, technical stakeholders
> **Prerequisites**: Basic understanding of web applications
> **Time**: 30-60 minutes to review

This section documents the system architecture, design decisions, and technical patterns used in the Missing Table application.

---

## 📚 Documentation in This Section

| Document | Description | Difficulty |
|----------|-------------|------------|
| **[Backend Structure](backend-structure.md)** | FastAPI, DAO patterns, database access | 🟡 Intermediate |
| **[Frontend Structure](frontend-structure.md)** | Vue.js, components, state management | 🟡 Intermediate |
| **[Authentication](authentication.md)** | Auth flow, JWT, role-based access | 🔴 Advanced |
| **[Database Schema](database-schema.md)** | Tables, relationships, constraints | 🟡 Intermediate |
| **[Clubs Architecture](../CLUBS_ARCHITECTURE.md)** | Clubs, teams, leagues separation | 🟡 Intermediate |
| **[AI Agents](ai-agents.md)** | Autonomous agent architecture | 🔴 Advanced |

---

## 🎯 System Overview

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │     Backend      │    │   Supabase      │
│  (Vue.js 3)     │◄──►│    (FastAPI)     │◄──►│  (PostgreSQL)   │
│  localhost:8081 │    │  localhost:8000  │    │ localhost:55321 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                │ Studio: :55323  │
                                                │ DB: :55322      │
                                                └─────────────────┘
```

### Technology Stack

**Frontend:**
- Vue.js 3 (Composition API)
- Pinia (State Management)
- Tailwind CSS
- Vite (Build Tool)

**Backend:**
- FastAPI (Python 3.13+)
- Pydantic (Data Validation)
- PyJWT (Authentication)
- uvicorn (ASGI Server)

**Database:**
- PostgreSQL (via Supabase)
- Row Level Security (RLS)
- Real-time subscriptions

**DevOps:**
- Docker & Docker Compose
- Kubernetes (GKE)
- Helm Charts
- GitHub Actions

---

## 🔑 Key Architectural Decisions

### 1. Backend-Centered Authentication

**Decision**: All authentication flows through the backend API.

**Why**:
- ✅ Resolves Kubernetes networking issues
- ✅ Better security (credentials stay server-side)
- ✅ Consistent API-first architecture
- ✅ Easier to test and monitor

**Flow**:
```
Frontend → Backend API → Supabase Auth
   ↓           ↓
  JWT      Manages
 Token     Sessions
```

See: [Authentication Documentation](authentication.md)

### 2. DAO (Data Access Object) Pattern

**Decision**: Separate data access logic from business logic.

**Why**:
- ✅ Supports multiple database backends (Supabase, SQLite)
- ✅ Easy to test (mock DAO in tests)
- ✅ Clean separation of concerns
- ✅ Consistent data access patterns

**Structure**:
```
backend/dao/
├── enhanced_data_access_fixed.py  # Main Supabase connection
├── local_data_access.py           # Local SQLite support
└── supabase_data_access.py        # Original implementation
```

See: [Backend Structure](backend-structure.md)

### 3. Component-Based Frontend

**Decision**: Vue 3 with Composition API and Pinia stores.

**Why**:
- ✅ Modern, reactive framework
- ✅ Great developer experience
- ✅ Strong TypeScript support
- ✅ Excellent tooling

**Structure**:
```
frontend/src/
├── components/          # Reusable components
│   ├── admin/          # Admin-specific components
│   ├── LeagueTable.vue
│   └── ScoresSchedule.vue
├── stores/             # Pinia state management
│   └── auth.js
└── router/             # Vue Router configuration
```

See: [Frontend Structure](frontend-structure.md)

### 4. Environment Isolation

**Decision**: Support local, dev, and prod environments with easy switching.

**Why**:
- ✅ Safe local development
- ✅ Cloud dev for team collaboration
- ✅ Production isolation
- ✅ Easy environment switching

**Implementation**:
```bash
./switch-env.sh local  # Local Supabase
./switch-env.sh prod   # Production (use with caution)
```

---

## 📊 Data Flow

### User Request Flow

```
1. User Action (Frontend)
   ↓
2. API Request (with JWT)
   ↓
3. Authentication Middleware
   ↓
4. Route Handler (FastAPI)
   ↓
5. DAO Layer (Data Access)
   ↓
6. Database (Supabase/PostgreSQL)
   ↓
7. Response (JSON)
   ↓
8. UI Update (Vue Reactivity)
```

### Authentication Flow

```
1. User Login (Frontend)
   ↓
2. POST /api/auth/login
   ↓
3. Backend validates credentials
   ↓
4. Supabase Auth verification
   ↓
5. JWT tokens generated
   ↓
6. User profile retrieved
   ↓
7. Session stored (frontend)
   ↓
8. Authenticated requests include JWT
```

See: [Authentication Documentation](authentication.md)

---

## 🗄️ Database Design

### Core Tables

```
teams ─────┐
           │
matches ───┼──── season ──── age_groups
           │
           └──── divisions ── match_types
                              │
                              └──── team_match_types

user_profiles ──── auth.users (Supabase)
```

### Key Relationships

- **Clubs** are organizations that field teams (e.g., "IFA")
- **Teams** belong to a club and a league, have matches as home or away
- **Leagues** are competition categories (e.g., "Homegrown", "Academy", "Elite")
- **Matches** belong to season, age group, division, match type
- **Match Types** define competition categories (league, friendly, tournament, etc.)
- **Team Match Types** assign specific match types to teams
- **User Profiles** extend Supabase auth with roles and metadata
- **Standings** calculated from match results

See: [Database Schema](database-schema.md)

---

## 🔐 Security Architecture

### Authentication & Authorization

**Roles**:
- `admin` - Full system access
- `team_manager` - Manage assigned team
- `user` - Read-only access (default)

**Security Layers**:
1. **JWT Authentication** - Token-based auth
2. **Role-Based Access Control (RBAC)** - Permission checks
3. **Row Level Security (RLS)** - Database-level policies
4. **API Rate Limiting** - Prevent abuse
5. **CORS Configuration** - Cross-origin protection

### Secret Management

**Principles**:
- 🔒 Never commit secrets to git
- 🔒 Use environment variables
- 🔒 Kubernetes Secrets in production
- 🔒 detect-secrets pre-commit hooks

See: [Security Documentation](../06-security/)

---

## 🧪 Testing Architecture

### Test Pyramid

```
    ┌──────┐
    │  E2E │  (Few)
    ├──────┤
    │ Integ│  (Some)
    ├──────┤
    │ Unit │  (Many)
    └──────┘
```

**Backend**:
- Unit tests (DAO, business logic)
- Integration tests (database, API)
- E2E tests (full workflows)

**Frontend**:
- Component tests (Vue Test Utils)
- Store tests (Pinia)
- E2E tests (Playwright - planned)

See: [Testing Documentation](../04-testing/)

---

## 🚀 Deployment Architecture

### Local Development
```
Docker Compose
├── Backend (uvicorn)
├── Frontend (npm serve)
└── Supabase (local)
```

### Cloud Deployment (GKE) - Hybrid Model
```
Google Kubernetes Engine (Public Services)
├── missing-table-dev namespace
│   ├── Backend Pods (FastAPI)
│   └── Frontend Pods (Vue.js)
└── Supabase Cloud (external)

Local K3s Cluster (Private Messaging)
└── match-scraper namespace
    ├── RabbitMQ (message broker)
    ├── Redis (result backend)
    └── Celery Worker Pods (2+ replicas)
```

**Architecture Decision**: Redis and Celery workers run exclusively on local K3s (Rancher Desktop) to reduce GKE costs (~$72/month → ~$5/month) while maintaining all async processing capabilities.

See: [Deployment Documentation](../05-deployment/)

---

## 🔄 Async Task Processing

### Architecture Overview

The system uses **Celery** with **RabbitMQ** and **Redis** for async task processing, enabling scalable, resilient match submission from external sources.

```
Match-Scraper (External)
         │
         │ HTTP POST
         ↓
┌────────────────────┐
│  FastAPI Backend   │  POST /api/matches/submit
│   (app.py)         │  GET /api/matches/task/{id}
└─────────┬──────────┘
          │ Queue Task
          ↓
┌────────────────────┐
│     RabbitMQ       │  Message Broker
│  (messaging ns)    │  Task Queue
└─────────┬──────────┘
          │ Distribute
          ↓
┌────────────────────┐
│  Celery Workers    │  Process Tasks
│  (2+ replicas)     │  Entity Resolution
└─────────┬──────────┘  Database Ops
          │ Store Result
          ↓
┌────────────────────┐
│      Redis         │  Result Backend
│  (messaging ns)    │  Task Status
└────────────────────┘
```

### Key Features

**Async Match Submission:**
- Immediate API response (~100ms)
- Background processing (~900ms)
- No client waiting
- Scalable with worker replicas

**Entity Resolution:**
- Match-scraper sends team **names** (not IDs)
- Workers automatically resolve to database IDs
- Handles missing entities gracefully
- Deduplication via `external_match_id`

**Resilience:**
- Automatic retries on failures
- Independent task processing
- Failed tasks don't block queue
- Observable via task status API

See: [Backend Structure - Async Architecture](backend-structure.md#-async-task-processing-architecture)

---

## 🤖 AI Agents Architecture

### Master/Sub-Agent Pattern

```
Master Agent (Orchestrator)
├── Scraper Agent (MLS Next)
└── Database Agent (API Integration)
```

**Use Case**: Automated MLS Next data collection

See: [AI Agents Documentation](ai-agents.md)

---

## 📖 Related Documentation

- **[Development Guide](../02-development/)** - Daily workflows
- **[Testing Strategy](../04-testing/)** - Test approach
- **[Deployment Guide](../05-deployment/)** - Deployment options
- **[Security Guide](../06-security/)** - Security practices

---

## 🎓 Learning Resources

### Recommended Reading Order

1. **New Developers**: Backend Structure → Frontend Structure → Database Schema
2. **Frontend Focused**: Frontend Structure → Authentication → Testing
3. **Backend Focused**: Backend Structure → Database Schema → Authentication
4. **DevOps**: Deployment → Security → Monitoring

### External Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js Guide](https://vuejs.org/guide/)
- [Supabase Docs](https://supabase.com/docs)
- [PostgreSQL Tutorial](https://www.postgresql.org/docs/)

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
