# Backend Applications Guide

## Overview

This backend contains two FastAPI applications:

## 🚀 **app.py** - Full Production Application
- **File**: `app.py` (1113+ lines)
- **Purpose**: Complete production application with all features
- **Endpoints**: 40+ API endpoints including:
  - Authentication (`/api/auth/*`)
  - Sports data (`/api/age-groups`, `/api/divisions`, `/api/seasons`, `/api/table`)
  - Team management (`/api/teams`, `/api/games`)
  - Admin functionality
  - Security monitoring
- **Dependencies**: 
  - Database (Supabase/PostgreSQL)
  - Redis for caching
  - Authentication system
  - Security monitoring (Logfire)
- **Run with**: `uvicorn app:app`

## 🧪 **test_minimal_app.py** - Minimal Test Version  
- **File**: `test_minimal_app.py` (100+ lines)
- **Purpose**: Minimal test application for development/testing only
- **Endpoints**: Only 4 basic endpoints:
  - `/health` - Health check
  - `/api/test` - Basic test
  - `/api/version` - Version info
  - `/` - Root info
- **Dependencies**: None (just FastAPI)
- **Run with**: `uvicorn test_minimal_app:app`

## ⚠️ **Important Notes**

### Frontend Compatibility
- **Frontend expects**: Full `app.py` with all sports API endpoints
- **Minimal app provides**: Only basic endpoints (causes 404 errors in frontend)

### When to Use Each

| Use Case | Application | Command |
|----------|-------------|---------|
| **Production** | `app.py` | `uvicorn app:app` |
| **Full Development** | `app.py` | `uvicorn app:app` |
| **Basic API Testing** | `test_minimal_app.py` | `uvicorn test_minimal_app:app` |
| **Health Checks Only** | `test_minimal_app.py` | `uvicorn test_minimal_app:app` |

### Current Helm Configuration

**Default (values.yaml)**: Uses `app:app` (full application)
```yaml
command:
  - "uvicorn"
  - "app:app"  # Full application
```

**For testing only**: Change to `test_minimal_app:app`
```yaml
command:
  - "uvicorn" 
  - "test_minimal_app:app"  # Minimal test version
```

## 🔧 Troubleshooting

### App.py Issues
If `app.py` fails to start, common issues:
1. **Database connection**: Ensure Supabase/PostgreSQL is accessible
2. **Logfire authentication**: Set `DISABLE_LOGFIRE=true` environment variable
3. **Missing dependencies**: Check all security/auth modules are available

### Frontend "Failed to fetch" errors
- Usually means backend is running `test_minimal_app.py` instead of `app.py`
- Frontend needs endpoints like `/api/age-groups`, `/api/seasons` that only exist in `app.py`

## 📝 Recent Changes

- **Removed**: `app_simple.py` (was causing confusion)
- **Added**: `test_minimal_app.py` (clearly documented as test-only)
- **Fixed**: Logfire import issue in `security_monitoring.py` (lazy initialization)
- **Updated**: Helm values to default to full `app:app`