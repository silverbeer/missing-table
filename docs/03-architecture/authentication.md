# Authentication Architecture Refactor: Client-Side to Backend-Centered

## Executive Summary

This document outlines the implementation plan to refactor the Missing Table authentication system from client-side Supabase authentication to a backend-centered approach. This change will resolve Kubernetes networking issues, improve security, and create a more maintainable architecture.

> **Update (2025-11-28):** Backend security monitoring hooks referenced later in this doc were removed from the codebase. Treat those sections as legacy notes only.

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Target Architecture](#target-architecture)
3. [Implementation Phases](#implementation-phases)
4. [Detailed Code Changes](#detailed-code-changes)
5. [Kubernetes Configuration](#kubernetes-configuration)
6. [Migration Strategy](#migration-strategy)
7. [Testing and Validation](#testing-and-validation)
8. [Benefits and Trade-offs](#benefits-and-trade-offs)

## Current State Analysis

### Current Architecture Problems

#### 1. **Networking Issues**
```
Frontend Pod (k8s) → [FAILS] → Supabase (127.0.0.1:54321)
Frontend Pod (k8s) → [FAILS] → Backend Pod (192.168.5.15:8000 LoadBalancer)
```

**Issues:**
- Frontend pods cannot reach `127.0.0.1:54321` (localhost from k8s pod perspective)
- LoadBalancer IP `192.168.5.15:8000` is not accessible in current setup
- Port-forwarding works for testing but not for production deployment

#### 2. **Current Authentication Flow**
```javascript
// Frontend stores/auth.js - CURRENT PROBLEMATIC APPROACH
const { data, error } = await supabase.auth.signInWithPassword({
  email,
  password,
});

// Direct client-side Supabase calls:
supabase.auth.signUp()           // ❌ Network fails in k8s
supabase.auth.signInWithPassword() // ❌ Network fails in k8s  
supabase.auth.signOut()          // ❌ Network fails in k8s
supabase.from('user_profiles')   // ❌ Network fails in k8s
```

#### 3. **Security Concerns**
- Supabase anon key exposed in frontend environment variables
- Direct database access from browser
- Auth state management scattered across frontend components

### Current Backend Implementation Status

**✅ Good News: Backend auth infrastructure already exists!**

```python
# backend/app.py - EXISTING ENDPOINTS
@app.post("/api/auth/signup")     # ✅ Already implemented
@app.post("/api/auth/login")      # ✅ Already implemented
@app.post("/api/auth/logout")     # ✅ Already implemented
@app.get("/api/auth/profile")     # ✅ Already implemented

# backend/auth.py - EXISTING AUTH MANAGER
class AuthManager:                # ✅ Already implemented
    def verify_token()            # ✅ JWT verification working
    def get_current_user()        # ✅ FastAPI dependency ready
    def require_role()            # ✅ Authorization working
```

## Target Architecture

### New Authentication Flow
```
Frontend Pod (k8s) → [k8s service] → Backend Pod → Supabase (external)
```

**Benefits:**
- ✅ Simple k8s internal networking
- ✅ All external connections handled by backend
- ✅ Centralized auth logic
- ✅ Better security and monitoring

### API Design

#### 1. **Authentication Endpoints**
```
POST /api/auth/login
POST /api/auth/signup  
POST /api/auth/logout
POST /api/auth/refresh
GET  /api/auth/me
PUT  /api/auth/profile
```

#### 2. **Session Management**
- Backend handles all Supabase JWT tokens
- Frontend receives simplified session tokens
- Automatic token refresh handled by backend

#### 3. **Frontend Changes**
```javascript
// NEW APPROACH - Backend API calls
const response = await fetch('/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
```

## Implementation Phases

### Phase 1: Backend API Enhancements ⏱️ ~4 hours

**Goal:** Ensure backend auth endpoints are complete and return frontend-friendly responses

#### 1.1 Update Login Endpoint Response
```python
# Current: Returns Supabase objects
# Target: Return clean JSON for frontend consumption

@app.post("/api/auth/login")
async def login(request: Request, user_data: UserLogin):
    # ... existing auth logic ...
    
    # NEW: Return frontend-friendly response
    return {
        "success": True,
        "user": {
            "id": response.user.id,
            "email": response.user.email,
            "profile": profile
        },
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_at": response.session.expires_at
        }
    }
```

#### 1.2 Add Missing Endpoints
```python
@app.post("/api/auth/refresh")
async def refresh_token(request: Request, refresh_data: RefreshToken):
    """Refresh JWT token using refresh token"""
    
@app.get("/api/auth/me")  
async def get_current_user_profile(current_user: dict = Depends(auth_manager.get_current_user)):
    """Get current user info - for frontend auth state"""
```

#### 1.3 Update CORS and Error Handling
- Ensure all auth endpoints have proper CORS
- Standardize error response format
- Add request/response logging

### Phase 2: Frontend Authentication Refactor ⏱️ ~6 hours

**Goal:** Replace all direct Supabase calls with backend API calls

#### 2.1 Update Auth Store (`frontend/src/stores/auth.js`)

**Before:**
```javascript
const login = async (email, password) => {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  // ... handle response
};
```

**After:**
```javascript
const login = async (email, password) => {
  try {
    setLoading(true);
    clearError();

    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Login failed');
    }

    const data = await response.json();
    
    // Store session data
    setUser(data.user);
    setSession(data.session);
    setProfile(data.user.profile);
    
    // Store tokens for API calls
    localStorage.setItem('auth_token', data.session.access_token);
    localStorage.setItem('refresh_token', data.session.refresh_token);

    return { success: true, user: data.user };
  } catch (error) {
    setError(error.message);
    return { success: false, error: error.message };
  } finally {
    setLoading(false);
  }
};
```

#### 2.2 Update All Auth Methods

| Current Supabase Method | New Backend API Call |
|------------------------|---------------------|
| `supabase.auth.signUp()` | `POST /api/auth/signup` |
| `supabase.auth.signInWithPassword()` | `POST /api/auth/login` |
| `supabase.auth.signOut()` | `POST /api/auth/logout` |
| `supabase.auth.getSession()` | `GET /api/auth/me` |
| `supabase.auth.refreshSession()` | `POST /api/auth/refresh` |
| `supabase.from('user_profiles')` | `GET /api/auth/profile` |

#### 2.3 Remove Supabase Client Dependencies
```javascript
// REMOVE these imports:
import { createClient } from '@supabase/supabase-js';
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// REMOVE environment variable dependencies:
// VUE_APP_SUPABASE_URL
// VUE_APP_SUPABASE_ANON_KEY
```

#### 2.4 Update API Client Configuration
```javascript
// frontend/src/config/api.js - UPDATE
const getApiUrl = () => {
  // Simplified - always use backend service
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    
    // If running on localhost (development), use port-forward
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8000';
    }
    
    // In k8s, use internal service name
    return 'http://missing-table-backend:8000';
  }
  
  return 'http://localhost:8000';
};
```

### Phase 3: Kubernetes Configuration Simplification ⏱️ ~2 hours

**Goal:** Simplify k8s networking now that frontend only talks to backend

#### 3.1 Update Helm Values
```yaml
# helm/missing-table/values.yaml
frontend:
  env:
    nodeEnv: "development"
    # REMOVE: supabaseUrl - no longer needed
    # REMOVE: supabaseAnonKey - no longer needed
    # UPDATE: Use internal k8s service
    apiUrl: "http://missing-table-backend:8000"
    vueAppDisableSecurity: "true"
```

#### 3.2 Verify Backend Configuration
```yaml
backend:
  env:
    databaseUrl: "postgresql://postgres:postgres@host.rancher-desktop.internal:54322/postgres"
    # Backend still needs Supabase connection for auth operations
    # Keep existing backend Supabase config
```

### Phase 4: Testing and Validation ⏱️ ~3 hours

**Goal:** Ensure all auth flows work end-to-end

#### 4.1 Update Login Uptime Test
```python
# scripts/login_uptime_test.py - UPDATE
async def test_login_process(self):
    """Test the complete login process - now tests backend API"""
    try:
        # Fill form as before...
        # Click login button as before...
        
        # NEW: Wait for successful API call to backend
        # Look for success indicators after backend login
        # Verify JWT token is stored in localStorage
        
        return True
    except Exception as e:
        return False
```

#### 4.2 Create Backend Auth Test
```python
# scripts/auth_backend_test.py - NEW
def test_auth_endpoints():
    """Test all backend auth endpoints directly"""
    # Test signup
    # Test login  
    # Test profile retrieval
    # Test token refresh
    # Test logout
```

### Phase 5: Cleanup and Documentation ⏱️ ~1 hour

#### 5.1 Remove Unused Dependencies
```json
// frontend/package.json - REMOVE
"@supabase/supabase-js": "^x.x.x"
```

#### 5.2 Update Documentation
- Update CLAUDE.md with new auth flow
- Document simplified k8s deployment
- Update troubleshooting guides

## Detailed Code Changes

### Backend Changes

#### 1. Enhanced Login Endpoint
> Login logging now uses structlog context binding (see `backend/app.py`).

```

### Frontend Changes

#### 1. Simplified Auth Store
```javascript
// frontend/src/stores/auth.js - COMPLETE REWRITE

import { reactive, computed } from 'vue';
import { addCSRFHeader, clearCSRFToken } from '../utils/csrf';

// Remove Supabase imports entirely

// Auth store
const state = reactive({
  user: null,
  session: null,
  profile: null,
  loading: false,
  error: null,
});

export const useAuthStore = () => {
  // Computed properties (keep existing)
  const isAuthenticated = computed(() => !!state.session);
  const isAdmin = computed(() => state.profile?.role === 'admin');
  // ... other computed properties

  // Helper functions
  const setLoading = loading => {
    state.loading = loading;
  };

  const setError = error => {
    state.error = error;
  };

  const clearError = () => {
    state.error = null;
  };

  const setUser = user => {
    state.user = user;
  };

  const setSession = session => {
    state.session = session;
    if (session?.access_token) {
      localStorage.setItem('auth_token', session.access_token);
      localStorage.setItem('refresh_token', session.refresh_token);
    }
  };

  const setProfile = profile => {
    state.profile = profile;
  };

  // NEW: API call helper with auth headers
  const apiCall = async (endpoint, options = {}) => {
    const token = localStorage.getItem('auth_token');
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      defaultHeaders.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(endpoint, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });

    if (response.status === 401) {
      // Token expired, try refresh
      await refreshToken();
      // Retry original request
      const retryToken = localStorage.getItem('auth_token');
      if (retryToken) {
        defaultHeaders.Authorization = `Bearer ${retryToken}`;
        return fetch(endpoint, {
          ...options,
          headers: {
            ...defaultHeaders,
            ...options.headers,
          },
        });
      }
    }

    return response;
  };

  // NEW: Auth actions using backend API
  const signup = async (email, password, displayName) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Signup failed');
      }

      const data = await response.json();
      return { success: true, message: data.message };

    } catch (error) {
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      setLoading(true);
      clearError();

      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();

      setUser(data.user);
      setSession(data.session);
      setProfile(data.user.profile);

      return { success: true, user: data.user };

    } catch (error) {
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      setLoading(true);
      
      const response = await apiCall('/api/auth/logout', {
        method: 'POST',
      });

      // Clear local state regardless of API response
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('refresh_token');
      clearCSRFToken();

      return { success: true };

    } catch (error) {
      // Still clear local state on error
      setUser(null);
      setSession(null);  
      setProfile(null);
      localStorage.clear();
      setError(error.message);
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  const refreshToken = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        throw new Error('No refresh token');
      }

      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      setSession(data.session);

      return { success: true };

    } catch (error) {
      // Refresh failed, force logout
      setUser(null);
      setSession(null);
      setProfile(null);
      localStorage.clear();
      return { success: false, error: error.message };
    }
  };

  const initialize = async () => {
    try {
      setLoading(true);

      // Check for existing token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        return;
      }

      // Get current user info from backend
      const response = await apiCall('/api/auth/me');

      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
        setProfile(data.user.profile);
        setSession({ access_token: token }); // Minimal session object
      } else {
        // Invalid token, clear storage
        localStorage.clear();
      }

    } catch (error) {
      console.error('Auth initialization error:', error);
      localStorage.clear();
    } finally {
      setLoading(false);
    }
  };

  // Return public interface
  return {
    // State
    state,
    
    // Computed
    isAuthenticated,
    isAdmin,
    isTeamManager,
    canManageTeam,
    userRole,
    userTeamId,
    
    // Actions
    signup,
    login,
    logout,
    initialize,
    refreshToken,
    apiCall,
    
    // Utilities
    setLoading,
    setError,
    clearError,
  };
};
```

## Kubernetes Configuration

### Simplified Helm Configuration

```yaml
# helm/missing-table/values.yaml - UPDATED

frontend:
  env:
    nodeEnv: "development"
    # REMOVED: supabaseUrl - no longer needed
    # REMOVED: supabaseAnonKey - no longer needed
    # SIMPLIFIED: Internal k8s networking only
    apiUrl: "http://missing-table-backend:8000"
    vueAppDisableSecurity: "true"

backend:
  env:
    # Backend still needs external Supabase connection
    databaseUrl: "postgresql://postgres:postgres@host.rancher-desktop.internal:54322/postgres"
    environment: "development"
    # ... keep existing backend config
```

### Network Architecture

**Before (Problematic):**
```
Frontend Pod → [FAILS] → External Supabase (127.0.0.1:54321)
Frontend Pod → [FAILS] → Backend Pod (192.168.5.15:8000)
```

**After (Working):**
```
Frontend Pod → [k8s ClusterIP] → Backend Pod → [host network] → External Supabase
```

## Migration Strategy

### Pre-Migration Checklist

1. **✅ Backup current database state**
   ```bash
   ./scripts/db_tools.sh backup
   ```

2. **✅ Verify existing backend auth endpoints work**
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"uptime_test@example.com","password":"Changeme!"}'
   ```

3. **✅ Document current frontend auth flows**
   - List all components using `useAuthStore()`
   - Identify all direct `supabase` calls

### Migration Steps

#### Step 1: Backend Preparation (Safe)
1. Deploy enhanced backend endpoints
2. Verify backward compatibility
3. Test all auth flows via API directly

#### Step 2: Frontend Development Build (Local Testing)
1. Update auth store
2. Test locally with port-forwarding
3. Verify all auth components work

#### Step 3: Kubernetes Deployment
1. Deploy new frontend with simplified config
2. Verify frontend → backend connectivity
3. Run comprehensive uptime tests

#### Step 4: Cleanup
1. Remove unused Supabase frontend dependencies  
2. Update documentation
3. Remove old environment variables

### Rollback Plan

If issues occur:

1. **Quick Rollback:** Revert Helm deployment
   ```bash
   helm rollback missing-table -n missing-table
   ```

2. **Backend Rollback:** Backend endpoints remain backward compatible

3. **Frontend Rollback:** Restore previous auth store version

### Data Migration

**Good news: No data migration needed!**
- Supabase database schema unchanged
- User accounts and profiles remain intact
- JWT tokens continue to work
- Only the client-side auth flow changes

## Testing and Validation

### Comprehensive Test Plan

#### 1. Backend API Testing

```bash
# Test all auth endpoints directly
curl -X POST localhost:8000/api/auth/signup \
  -d '{"email":"test@example.com","password":"password123","display_name":"Test User"}'

curl -X POST localhost:8000/api/auth/login \
  -d '{"email":"uptime_test@example.com","password":"Changeme!"}'

curl -X GET localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"

curl -X POST localhost:8000/api/auth/logout \
  -H "Authorization: Bearer <token>"
```

#### 2. Frontend Integration Testing

```javascript
// Test new auth store methods
const authStore = useAuthStore();

// Test signup
await authStore.signup('test@example.com', 'password123', 'Test User');

// Test login
await authStore.login('uptime_test@example.com', 'Changeme!');

// Test auth state
console.log(authStore.isAuthenticated.value);
console.log(authStore.userRole.value);

// Test logout
await authStore.logout();
```

#### 3. End-to-End Testing

```bash
# Run enhanced uptime test
cd backend && uv run python ../scripts/uptime_test.py

# Specific login test
cd backend && uv run python ../scripts/login_uptime_test.py
```

#### 4. Kubernetes Integration Testing

```bash
# Deploy and test in k8s
helm upgrade missing-table ./missing-table --namespace missing-table

# Verify internal networking
kubectl exec -n missing-table <frontend-pod> -- curl http://missing-table-backend:8000/health

# Test from browser (port-forward)
kubectl port-forward -n missing-table service/missing-table-frontend 8080:8080
```

### Test Scenarios

#### User Flows to Test:
1. **New user signup** → email verification → first login
2. **Existing user login** → profile loading → navigation
3. **Session expiry** → automatic token refresh
4. **Logout** → clean state cleanup
5. **Invalid credentials** → proper error handling
6. **Network failure** → graceful degradation

#### Component Testing:
1. **LoginForm.vue** → form submission → success/error states
2. **AuthNav.vue** → login/logout buttons → state updates
3. **Profile components** → protected routes → role checking
4. **Admin components** → role-based access → data loading

## Benefits and Trade-offs

### ✅ Benefits

#### 1. **Networking Simplification**
- **Before:** Complex k8s → external service networking
- **After:** Simple internal k8s service networking
- **Impact:** Eliminates all current connectivity issues

#### 2. **Security Improvements**
- **Before:** Supabase credentials exposed to browser
- **After:** Auth secrets contained in backend only
- **Impact:** Reduced attack surface, better credential management

#### 3. **Architecture Consistency**  
- **Before:** Mixed client-side/server-side patterns
- **After:** Consistent API-first architecture
- **Impact:** Easier to maintain, test, and extend

#### 4. **Deployment Reliability**
- **Before:** Environment-dependent networking configuration
- **After:** Consistent networking across all environments  
- **Impact:** Fewer deployment issues, easier troubleshooting

#### 5. **Performance Benefits**
- Reduced client-side JavaScript bundle (remove Supabase SDK)
- Centralized connection pooling to Supabase
- Better caching opportunities

### ⚠️ Trade-offs

#### 1. **Additional Backend Load**
- **Impact:** Backend handles all auth operations
- **Mitigation:** Use existing caching, monitoring
- **Assessment:** Minimal impact given current usage

#### 2. **Session Management Complexity**
- **Impact:** Need to handle JWT refresh properly
- **Mitigation:** Implement automatic refresh logic
- **Assessment:** Standard web app pattern

#### 3. **Development Testing**
- **Impact:** Need backend running for auth testing
- **Mitigation:** Good local development setup already exists
- **Assessment:** Consistent with existing workflow

### 📊 ROI Analysis

**Time Investment:** ~16 hours total implementation
**Time Saved:** Eliminate ongoing networking troubleshooting (~4+ hours/week)
**Security Value:** Significant improvement in auth security posture  
**Maintenance:** Simplified deployment and troubleshooting
**Technical Debt:** Reduces architectural inconsistencies

**Recommendation: Implement immediately**

## Next Steps

### Immediate Actions (Today)

1. **✅ Review this implementation plan**
2. **✅ Test existing backend auth endpoints**
3. **✅ Create implementation branch**

### Phase 1 (Tomorrow - 4 hours)
1. **Enhance backend auth endpoints**
2. **Test all endpoints with curl**
3. **Verify response formats**

### Phase 2 (Day 2 - 6 hours)  
1. **Refactor frontend auth store**
2. **Update all auth components**
3. **Test locally with port-forward**

### Phase 3 (Day 3 - 2 hours)
1. **Update Kubernetes configuration**  
2. **Deploy to k8s environment**
3. **Run comprehensive tests**

### Phase 4 (Day 4 - 3 hours)
1. **End-to-end validation**
2. **Performance testing**  
3. **Update documentation**

### Phase 5 (Day 5 - 1 hour)
1. **Final cleanup**
2. **Documentation updates**
3. **Team knowledge transfer**

---

## Conclusion

This refactor transforms the Missing Table authentication from a problematic client-side implementation to a robust, secure, and maintainable backend-centered architecture. The implementation resolves immediate Kubernetes networking issues while providing long-term architectural benefits.

The plan leverages existing backend infrastructure, minimizes changes to user-facing functionality, and creates a foundation for future authentication enhancements.

**Status: Ready for implementation**  
**Estimated completion: 5 days**  
**Risk level: Low** (leverages existing infrastructure)  
**Impact: High** (resolves critical deployment issues)